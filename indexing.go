package main

import (
	"bytes"
	"compress/gzip"
	"encoding/json"
	"errors"
	"fmt"
	"io/ioutil"
	"net/http"
	"os"
	"regexp"
	"strings"
	"sync"
	"time"
)

const mappingIndex = "stash-mappings"
const itemIndexPrefix = "items"

const rateLimit = 500 * time.Millisecond

var priceString = regexp.MustCompile(`\S+\s+(?P<Value>[0-9]*[.|/]?[0-9]+)\s+(?P<Currency>\w+)`)

func fetchItems(client *http.Client, updateCh chan itemUpdate) {
	currentID, err := getChangeID(client)
	if err != nil {
		panic(err)
	}

	for {
		start := time.Now()
		response, err := getNextStashes(client, currentID)
		if err != nil {
			fmt.Printf("Error getting stashes: %v\n", err)
			continue
		}

		if len(response.Stashes) == 0 {
			fmt.Println(">>> Reached the end of the stream, waiting for updates...")
			time.Sleep(rateLimit * 2)
			continue
		}

		updateCh <- itemUpdate{changeID: response.NextChangeID, stashes: response.Stashes}

		// Sleep so we don't request too frequently (more than once per second)
		end := time.Now()
		diff := end.Sub(start)
		if diff < rateLimit {
			time.Sleep(rateLimit - diff)
		}

		currentID = response.NextChangeID
	}
}

type itemUpdate struct {
	changeID string
	stashes  []PlayerStash
	deletes  []string
}

func diffStashLoop(client *http.Client, updateCh chan itemUpdate, persistCh chan itemUpdate) {
	for {
		select {
		case update := <-updateCh:
			// Filter out non-league items and format for indexing
			var leagueStashes []PlayerStash
			stashCount := 0
			for _, stash := range update.stashes {
				if stash.League == "Standard" ||
					stash.League == "Hardcore" ||
					strings.Contains(stash.League, " ") {
					continue
				}

				stashCount += 1
				stash.ItemIDs = make([]string, 0, len(stash.Items))
				formattedItems := make([]*IndexedItem, 0, len(stash.Items))
				for _, item := range stash.Items {
					formattedItems = append(formattedItems, item.ToIndexedItem())
					stash.ItemIDs = append(stash.ItemIDs, item.ID)
				}
				stash.FormattedItems = formattedItems
				stash.Items = nil

				leagueStashes = append(leagueStashes, stash)
			}

			filteredStashes := make([]PlayerStash, 0, len(leagueStashes))
			createCount, noopCount, updateCount := 0, 0, 0
			checkExisting := true

			if checkExisting {
				// Diff against existing items to detect no-ops
				start := time.Now()
				existingCh := make(chan []IndexedItem)
				numWorkers := 8
				for i := 0; i < numWorkers; i++ {
					go getExistingItems(leagueStashes[i*len(leagueStashes)/numWorkers:(i+1)*len(leagueStashes)/numWorkers], existingCh)
				}

				existingMap := make(map[string]IndexedItem, 5000)
				for i := 0; i < numWorkers; i++ {
					foundItems := <-existingCh
					for _, item := range foundItems {
						existingMap[item.ID] = item
					}
				}

				wrote := false
				for _, stash := range leagueStashes {
					var updates []*IndexedItem
					for _, item := range stash.FormattedItems {
						prevItem, ok := existingMap[item.ID]
						if !ok {
							item.create = true
							createCount++
							updates = append(updates, item)
							continue
						}

						prevItem.Account = item.Account
						prevItem.LastUpdated = item.LastUpdated
						prevItem.CreatedAt = item.CreatedAt

						bytesA, _ := json.Marshal(item)
						bytesB, _ := json.Marshal(prevItem)

						if bytes.Equal(bytesA, bytesB) {
							noopCount++
						} else {
							if !wrote {
								if _, err := os.Stat("cmp_prev_item.json"); errors.Is(err, os.ErrNotExist) {
									os.WriteFile("cmp_new_item.json", bytesA, 0644)
									os.WriteFile("cmp_prev_item.json", bytesB, 0644)
								}
								wrote = true
							}

							updateCount++
							updates = append(updates, item)
						}
					}

					filteredStashes = append(filteredStashes, PlayerStash{
						ID:                stash.ID,
						AccountName:       stash.AccountName,
						LastCharacterName: stash.LastCharacterName,
						Stash:             stash.Stash,
						StashType:         stash.StashType,
						League:            stash.League,
						ItemIDs:           stash.ItemIDs,
						FormattedItems:    updates,
						Public:            stash.Public,
					})
				}

				fmt.Printf("Looked up %v existing stashes in %v\n", len(leagueStashes), time.Since(start))
			}

			// Find removed items by comparing to previous stash contents
			deletes, err := diffStashes(client, leagueStashes)

			fmt.Printf("%d creates, %d updates, %d no-ops, %d deletes\n", createCount, updateCount, noopCount, len(deletes))

			if err != nil {
				fmt.Printf("Error diffing stashes: %v\n", err)
				continue
			}

			if !checkExisting {
				filteredStashes = leagueStashes
			}

			persistCh <- itemUpdate{changeID: update.changeID, stashes: filteredStashes, deletes: deletes}
		}
	}
}

func persistItemLoop(persistCh chan itemUpdate, changeCh chan string) {
	for {
		select {
		case update := <-persistCh:
			start := time.Now()

			itemCount := 0
			for _, stash := range update.stashes {
				itemCount += len(stash.FormattedItems)
			}

			var wg sync.WaitGroup
			numWorkers := 8
			for i := 0; i < numWorkers; i++ {
				updateChunk := itemUpdate{
					stashes: update.stashes[i*len(update.stashes)/numWorkers : (i+1)*len(update.stashes)/numWorkers],
					deletes: update.deletes[i*len(update.deletes)/numWorkers : (i+1)*len(update.deletes)/numWorkers],
				}

				wg.Add(1)
				go persistItems(updateChunk, &wg)
			}
			wg.Wait()

			delta := time.Since(start)
			fmt.Printf("Successfully persisted %d stashes (%d items) and %d removals in %s\n", len(update.stashes), itemCount, len(update.deletes), delta)
			changeCh <- update.changeID
		}
	}
}

func updateChangeIDLoop(client *http.Client, changeCh chan string) {
	for {
		select {
		case changeID := <-changeCh:
			// Update stored change ID
			if err := persistChangeID(client, changeID); err != nil {
				fmt.Printf("Error persisting change ID: %v\n", err)
			}
		}
	}
}

func getExistingItems(stashes []PlayerStash, existingCh chan []IndexedItem) {
	// Fetch stash mappings from db
	body := &bytes.Buffer{}
	body.WriteString(`{"ids": [`)
	first := true
	for _, stash := range stashes {
		for _, item := range stash.FormattedItems {
			if !first {
				body.WriteString(",")
			} else {
				first = false
			}
			body.WriteString(fmt.Sprintf(`"%s"`, item.ID))
		}
	}
	body.WriteString(`]}`)

	if first {
		existingCh <- []IndexedItem{}
		return
	}

	rawBody := string(body.Bytes())
	var items BulkItemResponse
	if err := doElasticsearchRequest("GET", itemIndexPrefix+"-archnemesis"+"/_mget", body, &items); err != nil {
		fmt.Println("Logging request body to existing_items_req.json")
		os.WriteFile("existing_items_req.json", []byte(rawBody), 0644)
		existingCh <- []IndexedItem{}
		return
	}

	foundCount := 0
	var foundItems []IndexedItem
	for _, entry := range items.Docs {
		if entry.Found {
			foundCount++
			entry.Source.ID = entry.ID
			foundItems = append(foundItems, entry.Source)
		}
	}

	//fmt.Printf("Worker sending %d existing items\n", len(foundItems))

	existingCh <- foundItems
}

func diffStashes(client *http.Client, stashes []PlayerStash) ([]string, error) {
	start := time.Now()

	// Fetch stash mappings from db
	body := &bytes.Buffer{}
	body.WriteString(`{"ids": [`)
	for i, stash := range stashes {
		if i > 0 {
			body.WriteString(",")
		}
		body.WriteString(fmt.Sprintf(`"%s"`, stash.ID))
	}
	body.WriteString(`]}`)

	rawBody := string(body.Bytes())
	var mappings StashMappingResponse
	if err := doElasticsearchRequest("GET", mappingIndex+"/_mget", body, &mappings); err != nil {
		fmt.Println("Logging request body to diff_req.json")
		os.WriteFile("diff_req.json", []byte(rawBody), 0644)
		return nil, err
	}

	oldStashes := make(map[string]map[string]bool, len(mappings.Docs))
	found := 0
	for _, doc := range mappings.Docs {
		if doc.Found {
			found += 1
		} else {
			continue
		}

		oldStashes[doc.ID] = make(map[string]bool, len(doc.Source.ItemIDs))
		for _, itemID := range doc.Source.ItemIDs {
			oldStashes[doc.ID][itemID] = true
		}
	}
	fmt.Printf("Found %d existing stashes to compare\n", found)

	// Compare to new stash mappings
	currentStashes := make(map[string]map[string]bool, 256)
	for _, stash := range stashes {
		if _, ok := oldStashes[stash.ID]; !ok {
			continue
		}

		currentStashes[stash.ID] = make(map[string]bool, len(stash.FormattedItems))
		for _, item := range stash.FormattedItems {
			currentStashes[stash.ID][item.ID] = true
		}
	}

	var deletes []string
	for stashID, stash := range oldStashes {
		for itemID := range stash {
			if _, ok := currentStashes[stashID][itemID]; !ok {
				deletes = append(deletes, itemID)
			}
		}
	}

	delta := time.Since(start)
	fmt.Printf("Diffed %v stashes in %v\n", len(stashes), delta)

	return deletes, nil
}

func persistItems(update itemUpdate, wg *sync.WaitGroup) {
	defer wg.Done()

	body := &bytes.Buffer{}
	itemCount := 0
	stashCount := 0

	start := time.Now()
	date := start.Format(ESDateFormat)

	if len(update.stashes) == 0 {
		fmt.Println("No stashes to persist")
		return
	}

	leagueIndex := itemIndexPrefix + "-archnemesis"
	for _, itemID := range update.deletes {
		body.WriteString(fmt.Sprintf(`{"update":{"_index":"%s","_id":"%s"}}`+"\n", leagueIndex, itemID))
		body.WriteString(fmt.Sprintf(`{"doc":{"removed_at":"%s"}}`+"\n", date))
	}

	for _, stash := range update.stashes {
		stashCount += 1

		index := strings.ToLower(fmt.Sprintf("%s-%v", itemIndexPrefix, stash.League))
		for _, item := range stash.FormattedItems {
			item.Account = stash.AccountName
			item.LastUpdated = date
			if item.create {
				item.CreatedAt = date
			}

			// Blank out item.ID so it doesn't get indexed
			id := item.ID
			item.ID = ""

			json, _ := json.Marshal(item)
			body.WriteString(fmt.Sprintf(`{"index":{"_index":"%s","_id":"%s"}}`+"\n", index, id))
			body.Write(json)
			body.WriteString("\n")
		}

		body.WriteString(fmt.Sprintf(`{"index":{"_index": "%s", "_id":"%s"}}`+"\n", mappingIndex, stash.ID))
		stashBytes, _ := json.Marshal(StashMapping{
			LastUpdated: date,
			ItemIDs:     stash.ItemIDs,
		})
		body.Write(stashBytes)
		body.WriteString("\n")

		itemCount += len(stash.FormattedItems)
	}

	rawBody := string(body.Bytes())
	compressed := &bytes.Buffer{}
	gz := gzip.NewWriter(compressed)
	if _, err := gz.Write(body.Bytes()); err != nil {
		panic(err)
	}
	if err := gz.Close(); err != nil {
		panic(err)
	}

	req, err := http.NewRequest("POST", ESURL+"_bulk", compressed)
	if err != nil {
		fmt.Printf("Error in request persisting items: %v\n", err)
		return
	}

	client := &http.Client{
		Timeout: 30 * time.Second,
	}
	setBasicAuth(req)
	req.Header.Set("Content-Type", "application/x-ndjson")
	req.Header.Set("Content-Encoding", "gzip")
	resp, err := client.Do(req)
	if err != nil {
		resp.Body.Close()
		fmt.Printf("Error in response persisting items: %v\n", err)
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		fmt.Printf("Error: status code %d\n", resp.StatusCode)
		fmt.Printf("Headers: %v\n", resp.Header)
		body, _ := ioutil.ReadAll(resp.Body)
		fmt.Println("Response Body:", string(body))
		fmt.Println("Logging request body to index_req.json")
		os.WriteFile("index_req.json", []byte(rawBody), 0644)
		return
	}
}

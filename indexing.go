package main

import (
	"bytes"
	"compress/gzip"
	"encoding/json"
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
			var leagueStashes []PlayerStash
			stashCount := 0
			for _, stash := range update.stashes {
				if stash.League == "Standard" ||
					stash.League == "Hardcore" ||
					strings.Contains(stash.League, " ") {
					continue
				}

				stashCount += 1
				formattedItems := make([]*IndexedItem, 0, len(stash.Items))
				for _, item := range stash.Items {
					formattedItems = append(formattedItems, item.ToIndexedItem())
				}
				stash.FormattedItems = formattedItems
				stash.Items = nil

				leagueStashes = append(leagueStashes, stash)
			}

			deletes, err := diffStashes(client, leagueStashes)

			if err != nil {
				fmt.Printf("Error diffing stashes: %v\n", err)
				continue
			}

			persistCh <- itemUpdate{changeID: update.changeID, stashes: leagueStashes, deletes: deletes}
		}
	}
}

func persistItemLoop(persistCh chan itemUpdate, changeCh chan string) {
	for {
		select {
		case update := <-persistCh:
			start := time.Now()

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
			fmt.Printf("Successfully persisted %d stashes and %d removals in %s\n", len(update.stashes), len(update.deletes), delta)
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
		stashItemIDs := make([]string, 0, len(stash.FormattedItems))
		for _, item := range stash.FormattedItems {
			item.Account = stash.AccountName
			item.LastUpdated = date
			stashItemIDs = append(stashItemIDs, item.ID)

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
			ItemIDs:     stashItemIDs,
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

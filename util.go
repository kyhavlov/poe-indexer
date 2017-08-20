package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"io/ioutil"
	"log"
	"net/http"
	"strings"
)

// Rebuilds the local mapping of stash IDs to item IDs from the index in elasticsearch
func (i *Indexer) rebuildStashIndex() {
	client := new(http.Client)

	scrollUrl := i.esUrl + "/items/item/_search?pretty=1&scroll=10m"

	// Query for all the items that haven't been removed yet
	scrollRequest := `{
	"from": 0,
	"size": 10000,
	"query": {
		"bool": {
			"must": {
				"exists": {"field": "id"}
			},
			"must_not": {
				"exists": {"field": "removed"}
			}
		}
	},
	"_source": ["id", "stashId"]}`

	var scrollResp ScrollResponse
	err := doRequest(client, "POST", scrollUrl, bytes.NewBufferString(scrollRequest), &scrollResp)
	if strings.Contains(err.Error(), "Unexpected status code 404") {
		return
	}
	if err != nil {
		panic(err)
	}

	queryUrl := i.esUrl + "/_search/scroll?pretty"
	queryBody := fmt.Sprintf(`{"scroll":"10m","scroll_id":"%s"}`, scrollResp.ScrollID)

	for {
		if len(scrollResp.Hits.Hits) == 0 {
			break
		}

		for _, hit := range scrollResp.Hits.Hits {
			if _, ok := i.stashItems[hit.Source.StashID]; !ok {
				i.stashItems[hit.Source.StashID] = make(map[string]bool)
			}
			i.stashItems[hit.Source.StashID][hit.Source.ID] = true
		}

		log.Printf("Parsed %d items", len(scrollResp.Hits.Hits))

		err := doRequest(client, "POST", queryUrl, bytes.NewBufferString(queryBody), &scrollResp)
		if err != nil {
			panic(err)
		}
	}

	err = i.persistStashIndex()
	if err != nil {
		panic(err)
	}
}

func doRequest(client *http.Client, method, url string, body io.Reader, out interface{}) error {
	req, err := http.NewRequest(method, "http://"+url, body)
	if err != nil {
		return err
	}

	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		log.Printf("Error: status code %d", resp.StatusCode)
		log.Printf("Headers: %v", resp.Header)

		body, err := ioutil.ReadAll(resp.Body)
		if err != nil {
			return err
		}

		log.Println("Response Body:", string(body))
		return fmt.Errorf("Unexpected status code %d", resp.StatusCode)
	}

	if out != nil {
		body, err := ioutil.ReadAll(resp.Body)
		if err != nil {
			return err
		}
		if err := json.Unmarshal(body, out); err != nil {
			return err
		}
	}

	return nil
}

type ScrollResponse struct {
	ScrollID string `json:"_scroll_id"`
	Hits     struct {
		Total int `json:"total"`
		Hits  []struct {
			Source struct {
				StashID string `json:"stashId"`
				ID      string `json:"id"`
			} `json:"_source"`
		} `json:"hits"`
	} `json:"hits"`
}

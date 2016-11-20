package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"io/ioutil"
	"log"
	"net/http"
	"os"
	"os/signal"
)

func main() {
	/*rebuildStashIndex()
	return*/

	indexer, err := NewIndexer()
	if err != nil {
		panic(err)
	}

	indexer.start()

	c := make(chan os.Signal, 1)
	signal.Notify(c)

	select {
	case <-c:
		fmt.Println("Got signal, shutting down")
		indexer.shutdown()

		// Wait for stash/api id to be persisted to disk/ES
		<-indexer.doneCh

		os.Exit(1)
	}
}

func standardPriceFilter(item *Item) bool {
	if item.Price != "" && item.League == "Standard" {
		return true
	}
	return false
}

func rebuildStashIndex() {
	client := new(http.Client)

	scrollUrl := "linux-server:9200/items/item/_search?pretty=1&scroll=10m"
	scrollRequest := `{
  	"from": 0, "size" : 10000,
      "query": {
          "exists" : { "field" : "id" }
      },
      "_source": ["id", "stashId"]
  }`

	var scrollResp ScrollResponse
	err := doRequest(client, "POST", scrollUrl, bytes.NewBufferString(scrollRequest), &scrollResp)
	if err != nil {
		panic(err)
	}

	queryUrl := "linux-server:9200/_search/scroll?pretty"
	queryBody := fmt.Sprintf(`{"scroll":"10m","scroll_id":"%s"}`, scrollResp.ScrollID)

	i, _ := NewIndexer()

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

		log.Println("Parsed 10000 items")

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

	if resp.StatusCode >= 400 {
		log.Printf("Error: status code %d", resp.StatusCode)
		log.Printf("Headers: %v", resp.Header)

		body, err := ioutil.ReadAll(resp.Body)
		if err != nil {
			return err
		}

		log.Println("response Body:", string(body))
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

const query = `{
	"from": %s, "size": %s,
    "query": {
        "exists" : { "field" : "id" }
    },
    "_source": ["id", "stashId"]
}`

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

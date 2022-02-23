package main

import (
	"encoding/json"
	"fmt"
	"io"
	"io/ioutil"
	"log"
	"net/http"
	"os"
	"time"
)

type StashMappingResponse struct {
	Docs []struct {
		ID     string `json:"_id"`
		Found  bool   `json:"found"`
		Source struct {
			ItemIDs []string `json:"item_ids"`
		} `json:"_source"`
	} `json:"docs"`
}

type StashMapping struct {
	LastUpdated string   `json:"last_updated,omitempty"`
	ItemIDs     []string `json:"item_ids"`
}

func setBasicAuth(req *http.Request) {
	user := os.Getenv("ES_USERNAME")
	pass := os.Getenv("ES_PASSWORD")
	req.SetBasicAuth(user, pass)
}

func doElasticsearchRequest(method, path string, body io.Reader, out interface{}) error {
	client := &http.Client{
		Timeout: 10 * time.Second,
	}
	req, err := http.NewRequest(method, ESURL+path, body)
	if err != nil {
		return err
	}

	setBasicAuth(req)
	req.Header.Set("Content-Type", "application/json")
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

func doDiscordRequest(body io.Reader) error {
	client := &http.Client{
		Timeout: 10 * time.Second,
	}
	req, err := http.NewRequest("POST", DiscordURL, body)
	if err != nil {
		return err
	}

	req.Header.Set("Content-Type", "application/json")
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

	return nil
}

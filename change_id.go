package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"net/http"
	"time"
)

func getChangeID() (string, error) {
	client := &http.Client{
		Timeout: 10 * time.Second,
	}
	req, err := http.NewRequest("GET", ESURL+"next-change-id/_doc/0", nil)
	if err != nil {
		return "", err
	}

	setBasicAuth(req)
	resp, err := client.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		log.Printf("Error: status code %d", resp.StatusCode)
		log.Printf("Headers: %v", resp.Header)
		body, _ := ioutil.ReadAll(resp.Body)
		log.Println("Response Body:", string(body))
		return "", fmt.Errorf("Unexpected status code %d", resp.StatusCode)
	}

	body, _ := ioutil.ReadAll(resp.Body)
	type changeResp struct {
		Source map[string]string `json:"_source"`
	}
	var cr changeResp
	if err := json.Unmarshal(body, &cr); err != nil {
		return "", err
	}

	return cr.Source["next_change_id"], nil
}

func persistChangeID(nextChangeID string) error {
	client := &http.Client{
		Timeout: 10 * time.Second,
	}

	body := &bytes.Buffer{}
	body.WriteString(fmt.Sprintf(`{"next_change_id": "%s"}`+"\n", nextChangeID))
	req, err := http.NewRequest("POST", ESURL+"next-change-id/_doc/0", body)
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
		body, _ := ioutil.ReadAll(resp.Body)
		log.Println("Response Body:", string(body))
		return fmt.Errorf("Unexpected status code %d", resp.StatusCode)
	}

	return nil
}

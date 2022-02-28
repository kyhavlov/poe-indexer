package main

import (
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"time"
)

const ESDateFormat = "2006-01-02T15:04:05-0700"

var (
	ESURL      = ""
	DiscordURL = ""
)

func main() {
	ESURL = os.Getenv("ES_URL")
	DiscordURL = os.Getenv("DISCORD_HOOK")
	if ESURL == "" {
		fmt.Println("ES_URL is not set")
		os.Exit(1)
	}

	fmt.Printf("ES_URL: %s\n", ESURL)
	fmt.Printf("DISCORD_HOOK: %s\n", DiscordURL)

	setupIndexes()

	// Set up the indexer to track items with a price from our chosen league
	client := &http.Client{Timeout: 30 * time.Second}
	fetchCh := make(chan itemUpdate, 4)
	formatCh := make(chan itemUpdate, 4)
	prunedItemsCh := make(chan itemUpdate, 4)
	persistCh := make(chan itemUpdate, 4)
	changeCh := make(chan string, 4)

	/*
		Stages of processing:
		1. Fetch items from POE stash tab api.
		2. Filter out the items from other leagues and format them for ES.
		3. (optional) Compare to existing items to avoid no-op writes.
		4. Diff the stash contents against their last known state to get removed items.
		5. Persist the created/updated/deleted items to ES.
		6. Update the last seen change ID and store it in ES.
	*/
	go fetchItems(client, fetchCh)
	go formatStashLoop(fetchCh, formatCh)
	go lookupItemLoop(formatCh, prunedItemsCh)
	go diffStashLoop(client, prunedItemsCh, persistCh)
	go persistItemLoop(persistCh, changeCh)
	//go expensiveSoldItemAlertLoop()
	updateChangeIDLoop(client, changeCh)

	// Wait for interrupt signal
	c := make(chan os.Signal, 1)
	signal.Notify(c)

	// Block and shutdown on receiving any signal
	<-c
	fmt.Println("Got signal, shutting down")

	os.Exit(1)
}

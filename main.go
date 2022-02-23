package main

import (
	"fmt"
	"os"
	"os/signal"
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
	updateCh := make(chan []PlayerStash, 4)
	persistCh := make(chan itemUpdate, 4)
	go diffStashLoop(updateCh, persistCh)
	go persistItemLoop(persistCh)

	go expensiveSoldItemAlertLoop()

	fetchItems(updateCh)

	// Wait for interrupt signal
	c := make(chan os.Signal, 1)
	signal.Notify(c)

	// Block and shutdown on receiving any signal
	<-c
	fmt.Println("Got signal, shutting down")

	os.Exit(1)
}

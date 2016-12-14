package main

import (
	"flag"
	"fmt"
	"os"
	"os/signal"
)

func main() {
	go chatbot()

	var esUrl string
	var league string
	flag.StringVar(&esUrl, "es", "127.0.0.1", "Elasticsearch address")
	flag.StringVar(&league, "league", "Standard", "League")
	flag.Parse()

	// Set up the indexer to track items with a price from our chosen league
	indexer, err := NewIndexer(esUrl + ":9200")
	if err != nil {
		panic(err)
	}
	indexer.filterFunc = func(item *Item) bool {
		if item.PriceChaos > 0 && item.League == league {
			return true
		}
		return false
	}
	indexer.start()

	// Wait for interrupt signal
	c := make(chan os.Signal, 1)
	signal.Notify(c)

	// Block and shutdown on receiving any signal
	<-c
	fmt.Println("Got signal, shutting down")
	indexer.shutdown()

	// Wait for stash/api id to be persisted to disk/ES
	<-indexer.doneCh

	os.Exit(1)
}

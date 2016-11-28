package main

import (
	"fmt"
	"os"
	"os/signal"
)

const elasticsearchUrl = "192.168.1.4:9200"

func main() {
	chatbot()
	return

	indexer, err := NewIndexer()
	if err != nil {
		panic(err)
	}

	indexer.start()

	// Wait for interrupt signal
	c := make(chan os.Signal, 1)
	signal.Notify(c)

	<-c
	fmt.Println("Got signal, shutting down")
	indexer.shutdown()

	// Wait for stash/api id to be persisted to disk/ES
	<-indexer.doneCh

	os.Exit(1)
}

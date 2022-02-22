package main

import (
	"bytes"
	"io/ioutil"
	"strings"
)

const stashIndexMapping = `{
  "mappings": {
    "enabled": false 
  }
}`

func setupIndexes() {
	err := doElasticsearchRequest("GET", mappingIndex, nil, nil)
	if err != nil && strings.Contains(err.Error(), "404") {
		body := bytes.NewBufferString(stashIndexMapping)
		if err := doElasticsearchRequest("PUT", mappingIndex, body, nil); err != nil {
			panic(err)
		}
	}

	itemIndex := itemIndexPrefix + "-archnemesis"
	err = doElasticsearchRequest("GET", itemIndex, nil, nil)
	if err != nil && strings.Contains(err.Error(), "404") {
		b, err := ioutil.ReadFile("item_index_mapping.json")
		if err != nil {
			panic(err)
		}
		body := bytes.NewBuffer(b)
		if err := doElasticsearchRequest("PUT", itemIndex, body, nil); err != nil {
			panic(err)
		}
	}
}

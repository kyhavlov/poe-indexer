package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"time"
)

const query = `{
	"query": {
	  "bool": {
		"must": [
		  {
			"range": {
			  "removed_at": {
				"gte": "%s"
			  }
			}
		  },
		  {
			"range": {
			  "price_chaos": {
				"gte": 1270
			  }
			}
		  }
		]
	  }
	}
  }`

type ItemQueryResponse struct {
	Hits struct {
		Hits []struct {
			Item Item `json:"_source"`
		} `json:"hits"`
	} `json:"hits"`
}

func expensiveSoldItemAlertLoop() {
	seenItems := make(map[string]bool)

	for {
		lastTime := time.Now()
		seenItems = alertOnExpensiveSoldItems(seenItems, lastTime.Add(-time.Minute))

		lastTime = lastTime.Add(time.Minute)
		time.Sleep(lastTime.Sub(time.Now()))
	}
}

func alertOnExpensiveSoldItems(duplicates map[string]bool, minTime time.Time) map[string]bool {
	date := time.Now().Add(-time.Minute)
	query := fmt.Sprintf(query, date.Format(ESDateFormat))

	body := bytes.NewBufferString(query)
	var resp ItemQueryResponse
	if err := doElasticsearchRequest("GET", "items-archnemesis/_search", body, &resp); err != nil {
		fmt.Println("Error running expensive item query:", err)
		return duplicates
	}

	newItems := make(map[string]bool)
	embeds := make([]DiscordEmbed, 0, len(resp.Hits.Hits))
	for _, item := range resp.Hits.Hits {
		if _, ok := duplicates[item.Item.ID]; ok {
			continue
		}

		newItems[item.Item.ID] = true

		// Prepare the message for discord
		embeds = append(embeds, makeDiscordEmbed(item.Item))
	}

	if len(embeds) == 0 {
		return newItems
	}

	jsonEncoded, _ := json.Marshal(embeds)
	jsonMsg := fmt.Sprintf(`{"username":"item-knower","avatar_url":"https://cdn.discordapp.com/app-icons/252665923981279232/926103f5ca846a96664478d71a2de821.png","embeds":%s}`, jsonEncoded)
	if err := doDiscordRequest(bytes.NewBufferString(jsonMsg)); err != nil {
		fmt.Println("Error sending discord message:", err)
		fmt.Println("Logging request body to discord_req.json")
		os.WriteFile("discord_req.json", []byte(jsonMsg), 0644)
	}

	return newItems
}

type DiscordEmbed struct {
	Title       string              `json:"title,omitempty"`
	Description string              `json:"description,omitempty"`
	Fields      []DiscordEmbedField `json:"fields,omitempty"`
}

type DiscordEmbedField struct {
	Name   string `json:"name,omitempty"`
	Value  string `json:"value,omitempty"`
	Inline bool   `json:"inline,omitempty"`
}

func makeDiscordEmbed(item Item) DiscordEmbed {
	embed := DiscordEmbed{
		Title:       item.Name,
		Description: item.TypeLine + "\n" + item.Note,
	}
	if embed.Title == "" {
		embed.Title = item.TypeLine
		embed.Description = item.Note
	}

	addStringArrayField := func(name string, array []string) {
		if len(array) > 0 {
			embed.Fields = append(embed.Fields, DiscordEmbedField{
				Name:  name,
				Value: strings.Join(array, "\n"),
			})
		}
	}

	if item.Extended.Category == "gems" {
		for _, prop := range item.Properties {
			if prop.Name == "Level" {
				embed.Fields = append(embed.Fields, DiscordEmbedField{
					Name:  "Gem Level",
					Value: prop.Values[0][0],
				})
			}
		}
	}

	addStringArrayField("Enchant Mods", item.EnchantMods)
	addStringArrayField("Implicit Mods", item.ImplicitMods)
	addStringArrayField("Explicit Mods", item.ExplicitMods)
	addStringArrayField("Crafted Mods", item.CraftedMods)
	addStringArrayField("Utility Mods", item.UtilityMods)

	if len(item.Influences) > 0 {
		for influence := range item.Influences {
			embed.Fields = append(embed.Fields, DiscordEmbedField{
				Name:  strings.Title(influence),
				Value: "\u200b",
			})
		}
	}

	if item.Synthesised {
		embed.Fields = append(embed.Fields, DiscordEmbedField{
			Name:  "Synthesised",
			Value: "\u200b",
		})
	}

	if item.Fractured {
		embed.Fields = append(embed.Fields, DiscordEmbedField{
			Name:  "Fractured",
			Value: "\u200b",
		})
	}

	if item.Duplicated {
		embed.Fields = append(embed.Fields, DiscordEmbedField{
			Name:  "Duplicated",
			Value: "\u200b",
		})
	}

	if item.Split {
		embed.Fields = append(embed.Fields, DiscordEmbedField{
			Name:  "Split",
			Value: "\u200b",
		})
	}

	if item.Searing {
		embed.Fields = append(embed.Fields, DiscordEmbedField{
			Name:  "Searing",
			Value: "\u200b",
		})
	}

	if item.Tangled {
		embed.Fields = append(embed.Fields, DiscordEmbedField{
			Name:  "Tangled",
			Value: "\u200b",
		})
	}

	if item.Corrupted {
		embed.Fields = append(embed.Fields, DiscordEmbedField{
			Name:  "Corrupted",
			Value: "\u200b",
		})
	}

	if !item.Identified {
		embed.Fields = append(embed.Fields, DiscordEmbedField{
			Name:  "Unidentified",
			Value: "\u200b",
		})
	}

	if len(item.Sockets) > 0 {
		groupCounts := make(map[int]int)
		for _, socket := range item.Sockets {
			groupCounts[socket.Group]++
		}
		maxCount := 0
		for _, count := range groupCounts {
			if count > maxCount {
				maxCount = count
			}
		}
		embed.Fields = append(embed.Fields, DiscordEmbedField{
			Name:   "Links",
			Value:  fmt.Sprintf("%d", maxCount),
			Inline: true,
		})
		embed.Fields = append(embed.Fields, DiscordEmbedField{
			Name:   "Sockets",
			Value:  fmt.Sprintf("%d", len(item.Sockets)),
			Inline: true,
		})
	}

	return embed
}

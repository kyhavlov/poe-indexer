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

	fmt.Printf("Sending %d sold items to Discord\n", len(embeds))

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
	embed.Description += fmt.Sprintf("\nilvl: %d", item.Ilvl)

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
			if prop.Name == "Quality" {
				embed.Fields = append(embed.Fields, DiscordEmbedField{
					Name:  "Gem Quality",
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

	influenceRollup := ""
	appendMod := func(mod string) {
		if influenceRollup != "" {
			influenceRollup += "\n" + strings.Title(mod)
		}
	}

	if len(item.Influences) > 0 {
		for influence := range item.Influences {
			appendMod(influence)
		}
	}

	if item.Synthesised {
		appendMod("Synthesised")
	}

	if item.Fractured {
		appendMod("Fractured")
	}

	if item.Duplicated {
		appendMod("Duplicated")
	}

	if item.Split {
		appendMod("Split")
	}

	if item.Searing {
		appendMod("Searing")
	}

	if item.Tangled {
		appendMod("Tangled")
	}

	if item.Corrupted {
		appendMod("Corrupted")
	}

	if !item.Identified {
		appendMod("Unidentified")
	}

	if influenceRollup != "" {
		embed.Fields = append(embed.Fields, DiscordEmbedField{
			Name:  influenceRollup,
			Value: "\u200b",
		})
	}

	if len(item.Sockets) > 0 {
		colorMap := map[string]string{"S": "R", "D": "G", "I": "B", "G": "W", "A": "A"}
		groupCounts := make(map[int]int)
		colorCounts := make(map[string]int)
		for _, socket := range item.Sockets {
			groupCounts[socket.Group]++
			colorCounts[colorMap[socket.Attr]]++
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

		socketStr := fmt.Sprintf("%d\n", len(item.Sockets))
		for color, count := range colorCounts {
			socketStr += strings.Repeat(color, count)
		}
		embed.Fields = append(embed.Fields, DiscordEmbedField{
			Name:   "Sockets",
			Value:  socketStr,
			Inline: true,
		})
	}

	return embed
}

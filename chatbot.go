package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"net/http"
	"os"
	"regexp"
	"sort"
	"strconv"
	"strings"

	"github.com/bwmarrin/discordgo"
)

var (
	BotID string
)

func chatbot() {
	// Create a new Discord session using the provided bot token.
	token := os.Getenv("DISCORD_TOKEN")
	if token == "" {
		log.Println("DISCORD_TOKEN var not found, chatbot disabled")
		return
	}
	dg, err := discordgo.New("Bot " + token)
	if err != nil {
		fmt.Println("error creating Discord session,", err)
		return
	}

	// Get the account information.
	u, err := dg.User("@me")
	if err != nil {
		fmt.Println("error obtaining account details,", err)
	}

	// Store the account ID for later use.
	BotID = u.ID

	// Register messageCreate as a callback for the messageCreate events.
	dg.AddHandler(messageCreate)

	// Open the websocket and begin listening.
	err = dg.Open()
	if err != nil {
		fmt.Println("error opening connection,", err)
		return
	}

	fmt.Println("Bot is now running.  Press CTRL-C to exit.")
	// Simple way to keep program running until CTRL-C is pressed.
	<-make(chan struct{})
	return
}

// This function will be called (due to AddHandler above) every time a new
// message is created on any channel that the autenticated bot has access to.
func messageCreate(s *discordgo.Session, m *discordgo.MessageCreate) {

	// Ignore all messages created by the bot itself
	if m.Author.ID == BotID {
		return
	}

	ch, err := s.Channel(m.ChannelID)
	if err != nil {
		log.Printf("Error getting channel name: %v", err)
		return
	}

	// Ignore messages in channels except 'price-check'
	if ch.Name != "price-check" {
		return
	}

	log.Println(m.Content)

	if !strings.HasPrefix(m.Content, "!pc ") {
		return
	}

	// Parse the item from clipboard format
	raw := strings.TrimPrefix(m.Content, "!pc ")
	item, err := parseClipboardItem(raw)
	if err != nil {
		message := fmt.Sprintf("%s: Error parsing item: %v", m.Author.Username, err)
		_, _ = s.ChannelMessageSend(m.ChannelID, message)
		return
	}

	encoded, err := json.Marshal(item)
	if err != nil {
		message := fmt.Sprintf("%s: Error encoding item: %v", m.Author.Username, err)
		_, _ = s.ChannelMessageSend(m.ChannelID, message)
		return
	}

	// _, _ = s.ChannelMessageSend(m.ChannelID, fmt.Sprintf("Item JSON: ```%s```", encoded))

	body := &bytes.Buffer{}
	body.WriteString(fmt.Sprintf("[%s]", encoded))

	req, err := http.NewRequest("POST", "http://localhost:8080/price", body)
	if err != nil {
		log.Printf("Error creating request: %v", err)
		return
	}

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		log.Printf("Error querying price server: %v", err)
		_, _ = s.ChannelMessageSend(m.ChannelID, fmt.Sprintf("%s: Error querying price server "+
			"(currently only normal, rare and unique weapons can be priced)", m.Author.Username))
		return
	}
	defer resp.Body.Close()

	responseBody, _ := ioutil.ReadAll(resp.Body)

	var priceMap []map[string]float32
	var prices Prices
	err = json.Unmarshal(responseBody, &priceMap)

	for label, weight := range priceMap[0] {
		if label != "estimate" {
			prices = append(prices, Price{label, weight})
		}
	}
	sort.Sort(prices)

	outputFormat := `Price Suggestions  [Weighted Average: %0.2f chaos]
Confidence | Price Interval
--------------------------------------
`
	priceOutput := fmt.Sprintf(outputFormat, priceMap[0]["estimate"])
	for _, p := range prices {
		line := fmt.Sprintf("%5.2f%%     | %s\n", p.Weight, p.Range)
		priceOutput = priceOutput + line
	}

	_, _ = s.ChannelMessageSend(m.ChannelID, fmt.Sprintf("%s:```%s```", m.Author.Username, priceOutput))
}

var rarities = map[string]int{
	"Normal": 0,
	"Magic":  1,
	"Rare":   2,
	"Unique": 3,
}

// GGG pls
var colors = map[string]string{
	"G": "D",
	"B": "I",
	"R": "S",
	"W": "G",
}

func parseClipboardItem(raw string) (*Item, error) {
	item := &Item{}
	item.Requirements = make([]Property, 0)
	item.Properties = make([]Property, 0)

	sections := strings.Split(raw, "--------")
	raw = strings.Replace(raw, " (augmented)", "", -1)

	// First section is the rarity and base type
	lines := strings.Split(strings.TrimSpace(sections[0]), "\n")
	rarity := regexp.MustCompile("Rarity: (.+)")

	m := rarity.FindStringSubmatch(lines[0])
	if m == nil {
		return nil, fmt.Errorf("No rarity found")
	}
	item.FrameType = rarities[m[1]]
	item.TypeLine = strings.TrimPrefix(lines[len(lines)-1], "<<set:MS>><<set:M>><<set:S>>")

	// Parse sockets, format: (Sockets: G-G B R-R-G)
	sockets := regexp.MustCompile("Sockets: (.+\\S)")
	socketsFound := sockets.FindStringSubmatch(raw)

	if socketsFound != nil {
		item.Sockets = make([]Socket, 0)
		groups := strings.Split(socketsFound[1], " ")
		for n, group := range groups {
			groupSockets := strings.Split(group, "-")
			for _, attr := range groupSockets {
				item.Sockets = append(item.Sockets, Socket{n, colors[attr]})
			}
		}
	}

	// Parse req/properties/stats/ilvl
	property := regexp.MustCompile("(.+): [\\+\\-]?(\\d+\\.?\\d*(?:\\-\\d+\\.?\\d*)?)%?,? ?(\\d+\\.?\\d*(?:\\-\\d+\\.?\\d*)?)?")
	properties := make(map[string][]string)

	propsFound := property.FindAllStringSubmatch(raw, -1)
	for _, p := range propsFound {
		// On properties without multiple number ranges (like elemental damage) skip the last group because it'll be empty
		if p[len(p)-1] == "" {
			properties[p[1]] = p[2:3]
		} else {
			properties[p[1]] = p[2:]
		}
	}

	if val, ok := properties["Item Level"]; ok {
		v, err := strconv.Atoi(val[0])
		if err != nil {
			return nil, fmt.Errorf("Invalid item level format")
		}
		item.Ilvl = v
		delete(properties, "Item Level")
	}

	// Requirements first
	reqNames := []string{"Level", "Str", "Dex", "Int"}
	for _, req := range reqNames {
		if val, ok := properties[req]; ok {
			item.Requirements = append(item.Requirements, makeProperty(req, val...))
			delete(properties, req)
		}
	}
	sort.Sort(item.Requirements)

	// Everything that's left should be a property
	for name, val := range properties {
		item.Properties = append(item.Properties, makeProperty(name, val...))
	}
	sort.Sort(item.Properties)

	// Now we work backward from the end, to prune corruption/flavor text
	// Check for corruption (it appears in the very last section, by itself)
	if strings.TrimSpace(sections[len(sections)-1]) == "Corrupted" {
		item.Corrupted = true
		sections = sections[:len(sections)-1]
	}

	// Check if we can stop now (tabula or white item)
	for _, p := range propsFound {
		if strings.Contains(sections[len(sections)-1], p[0]) {
			return item, nil
		}
	}

	// Take the flavor text section out if it's a unique
	if item.FrameType == rarities["Unique"] {
		sections = sections[:len(sections)-1]
	}

	// If this last section has more than 1 mod, assume it's explicit mods
	if strings.Count(strings.TrimSpace(sections[len(sections)-1]), "\n") > 1 {
		item.ExplicitMods = make([]string, 0)
		lines := strings.Split(strings.TrimSpace(sections[len(sections)-1]), "\n")
		modsFound := make(map[string]bool)
		number := regexp.MustCompile("(\\d+\\.?\\d*)")

		for _, line := range lines {
			numbers := number.FindAllStringSubmatch(line, -1)
			modName := line
			for _, num := range numbers {
				modName = strings.Replace(modName, num[1], "X", 1)
			}

			// Add as an explicit mod if we haven't seen it yet, otherwise it's a crafted mod
			// because it shows up twice
			if _, ok := modsFound[modName]; !ok {
				item.ExplicitMods = append(item.ExplicitMods, line)
			} else {
				if item.CraftedMods == nil {
					item.CraftedMods = make([]string, 0)
				}
				item.CraftedMods = append(item.CraftedMods, line)
			}

			modsFound[modName] = true
		}

		sections = sections[:len(sections)-1]
	}

	// If there's any requirements in the next section back, we're done
	for _, p := range propsFound {
		if strings.Contains(sections[len(sections)-1], p[0]) {
			return item, nil
		}
	}

	item.ImplicitMods = strings.Split(strings.TrimSpace(sections[len(sections)-1]), "\n")

	return item, nil
}

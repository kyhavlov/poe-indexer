package main

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"net/http"
	"time"
)

type Item struct {
	// Derived metadata fields
	Account       string     `json:"account,omitempty"`
	StashID       string     `json:"stashId,omitempty"`
	Created       int64      `json:"created,omitempty"`
	LastUpdated   string     `json:"last_updated,omitempty"`
	Removed       int64      `json:"removed,omitempty"`
	PriceValue    JSONDouble `json:"price_value,omitempty"`
	PriceCurrency string     `json:"price_currency,omitempty"`

	Verified          bool     `json:"verified,omitempty"`
	Ilvl              int      `json:"ilvl,omitempty"`
	Support           bool     `json:"support,omitempty"`
	ID                string   `json:"id,omitempty"`
	Sockets           []Socket `json:"sockets,omitempty"`
	Name              string   `json:"name,omitempty"`
	TypeLine          string   `json:"typeLine,omitempty"`
	BaseType          string   `json:"baseType,omitempty"`
	LockedToCharacter bool     `json:"lockedToCharacter,omitempty"`
	Note              string   `json:"note,omitempty"`
	FrameType         int      `json:"frameType,omitempty"`
	X                 int      `json:"x,omitempty"`
	Y                 int      `json:"y,omitempty"`
	InventoryID       string   `json:"inventoryId,omitempty"`
	TalismanTier      int      `json:"talismanTier,omitempty"`
	AbyssJewel        bool     `json:"abyssJewel,omitempty"`
	StackSize         int      `json:"stackSize,omitempty"`
	MaxStackSize      int      `json:"maxStackSize,omitempty"`

	Identified  bool            `json:"identified,omitempty"`
	Corrupted   bool            `json:"corrupted"`
	Duplicated  bool            `json:"duplicated,omitempty"`
	Split       bool            `json:"split,omitempty"`
	Elder       bool            `json:"elder,omitempty"`
	Shaper      bool            `json:"shaper,omitempty"`
	Searing     bool            `json:"searing,omitempty"`
	Tangled     bool            `json:"tangled,omitempty"`
	Synthesised bool            `json:"synthesised,omitempty"`
	Fractured   bool            `json:"fractured,omitempty"`
	Influences  map[string]bool `json:"influences,omitempty"`

	AdditionalProperties  Properties `json:"additionalProperties,omitempty"`
	NotableProperties     Properties `json:"notableProperties,omitempty"`
	Properties            Properties `json:"properties,omitempty"`
	Requirements          Properties `json:"requirements,omitempty"`
	NextLevelRequirements Properties `json:"nextLevelRequirements,omitempty"`
	ImplicitMods          []string   `json:"implicitMods,omitempty"`
	FracturedMods         []string   `json:"fracturedMods,omitempty"`
	ExplicitMods          []string   `json:"explicitMods,omitempty"`
	CraftedMods           []string   `json:"craftedMods,omitempty"`
	VeiledMods            []string   `json:"veiledMods,omitempty"`
	EnchantMods           []string   `json:"enchantMods,omitempty"`
	UtilityMods           []string   `json:"utilityMods,omitempty"`
	Extended              Extended   `json:"extended,omitempty"`
}

type JSONDouble float64

func (d JSONDouble) MarshalJSON() ([]byte, error) {
	return []byte(fmt.Sprintf("%.1f\n", d)), nil
}

type Extended struct {
	Category      string   `json:"category,omitempty"`
	Subcategories []string `json:"subcategories,omitempty"`
	Prefixes      int      `json:"prefixes,omitempty"`
	Suffixes      int      `json:"suffixes,omitempty"`
}

type Socket struct {
	Group int    `json:"group"`
	Attr  string `json:"attr"`
	Color string `json:"sColour"`
}

type Property struct {
	Name string `json:"name"`

	// Only grab the first item of each value tuple to avoid serializing to type
	// []interface{}, from things like ["asdf", 0]. The second item of the value
	// tuple seems to never be useful anyway
	Values [][1]string `json:"values"`

	DisplayMode int     `json:"displayMode"`
	Progress    float32 `json:"progress"`
}

func makeProperty(name string, val ...string) Property {
	p := Property{
		Name:   name,
		Values: make([][1]string, 0),
	}
	for _, v := range val {
		p.Values = append(p.Values, [1]string{v})
	}
	return p
}

type Properties []Property

func (a Properties) Len() int           { return len(a) }
func (a Properties) Swap(i, j int)      { a[i], a[j] = a[j], a[i] }
func (a Properties) Less(i, j int) bool { return a[i].Name < a[j].Name }

type Value struct {
	Name string `json:"name"`
}

type Price struct {
	Range  string
	Weight float32
}
type Prices []Price

func (a Prices) Len() int           { return len(a) }
func (a Prices) Swap(i, j int)      { a[i], a[j] = a[j], a[i] }
func (a Prices) Less(i, j int) bool { return a[i].Weight > a[j].Weight }

type APIResponse struct {
	ID           string `json:"-"`
	NextChangeID string `json:"next_change_id"`
	Stashes      []PlayerStash
}

type PlayerStash struct {
	AccountName       string  `json:"accountName"`
	LastCharacterName string  `json:"lastCharacterName"`
	ID                string  `json:"id"`
	Stash             string  `json:"stash"`
	StashType         string  `json:"stashType"`
	Items             []*Item `json:"items"`
	Public            bool    `json:"public"`
	League            string  `json:"league"`
}

func getNextStashes(currentID string, client *http.Client) (*APIResponse, error) {
	start := time.Now()
	req, err := http.NewRequest("GET", "http://api.pathofexile.com/public-stash-tabs?id="+currentID, nil)
	if err != nil {
		fmt.Printf("Error creating request: %v\n", err)
		return nil, err
	}

	response, err := client.Do(req)
	if err != nil {
		fmt.Printf("Error getting request: %v\n", err)
		return nil, err
	}
	defer response.Body.Close()

	bytes, err := ioutil.ReadAll(response.Body)
	if err != nil {
		fmt.Printf("Error reading response body: %v\n", err)
		return nil, err
	}

	var stashes APIResponse
	err = json.Unmarshal(bytes, &stashes)
	if err != nil {
		log.Printf("Error parsing json: %v\n", err)
		log.Printf("len: %v\n", len(bytes))
		return nil, err
	}

	delta := time.Since(start)
	fmt.Printf("Fetched %v stashes in %v\n", len(stashes.Stashes), delta)

	return &stashes, err
}

package main

// This file contains structs for deserializing the response data from the
// public stash tab api

type StashTabResponse struct {
	ID           string `json:"-"`
	NextChangeID string `json:"next_change_id"`
	Stashes      []*Stash
}

type Stash struct {
	AccountName       string  `json:"accountName"`
	LastCharacterName string  `json:"lastCharacterName"`
	ID                string  `json:"id"`
	Stash             string  `json:"stash"`
	StashType         string  `json:"stashType"`
	Items             []*Item `json:"items"`
	Public            bool    `json:"public"`
}

type Item struct {
	// Derived metadata fields
	Price       string  `json:"price,omitempty"`
	PriceChaos  float64 `json:"price_chaos,omitempty"`
	Account     string  `json:"account,omitempty"`
	StashID     string  `json:"stashId,omitempty"`
	Created     int64   `json:"created,omitempty"`
	LastUpdated int64   `json:"last_updated,omitempty"`
	Removed     int64   `json:"removed,omitempty"`

	Verified          bool     `json:"verified,omitempty"`
	Ilvl              int      `json:"ilvl"`
	Support           bool     `json:"support,omitempty"`
	League            string   `json:"league,omitempty"`
	ID                string   `json:"id,omitempty"`
	Sockets           []Socket `json:"sockets,omitempty"`
	Name              string   `json:"name,omitempty"`
	TypeLine          string   `json:"typeLine"`
	Identified        bool     `json:"identified,omitempty"`
	Corrupted         bool     `json:"corrupted"`
	LockedToCharacter bool     `json:"lockedToCharacter,omitempty"`
	Note              string   `json:"note,omitempty"`
	FrameType         int      `json:"frameType"`
	X                 int      `json:"x,omitempty"`
	Y                 int      `json:"y,omitempty"`
	InventoryID       string   `json:"inventoryId,omitempty"`

	AdditionalProperties  Properties `json:"additionalProperties,omitempty"`
	Properties            Properties `json:"properties,omitempty"`
	Requirements          Properties `json:"requirements,omitempty"`
	NextLevelRequirements Properties `json:"nextLevelRequirements,omitempty"`
	ImplicitMods          []string   `json:"implicitMods,omitempty"`
	ExplicitMods          []string   `json:"explicitMods,omitempty"`
	CraftedMods           []string   `json:"craftedMods,omitempty"`
}

type Socket struct {
	Group int    `json:"group"`
	Attr  string `json:"attr"`
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

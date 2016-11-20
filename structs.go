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
	Price       string `json:"price"`
	Account     string `json:"account"`
	StashID     string `json:"stashId"`
	Created     int64  `json:"created,omitempty"`
	LastUpdated int64  `json:"last_updated"`
	Removed     int64  `json:"removed,omitempty"`

	Verified          bool      `json:"verified"`
	Ilvl              int       `json:"ilvl"`
	Support           bool      `json:"support"`
	League            string    `json:"league"`
	ID                string    `json:"id"`
	Sockets           []*Socket `json:"sockets,omitempty"`
	Name              string    `json:"name"`
	TypeLine          string    `json:"typeLine"`
	Identified        bool      `json:"identified"`
	Corrupted         bool      `json:"corrupted,omitempty"`
	LockedToCharacter bool      `json:"lockedToCharacter"`
	Note              string    `json:"note,omitempty"`
	FrameType         int       `json:"frameType"`
	X                 int       `json:"x"`
	Y                 int       `json:"y"`
	InventoryID       string    `json:"inventoryId"`

	AdditionalProperties  []*Property `json:"additionalProperties,omitempty"`
	Properties            []*Property `json:"properties,omitempty"`
	Requirements          []*Property `json:"requirements,omitempty"`
	NextLevelRequirements []*Property `json:"nextLevelRequirements,omitempty"`
	ImplicitMods          []string    `json:"implicitMods,omitempty"`
	ExplicitMods          []string    `json:"explicitMods,omitempty"`
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

type Value struct {
	Name string `json:"name"`
}

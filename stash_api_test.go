package main

import (
	"encoding/json"
	"testing"

	"github.com/stretchr/testify/require"
)

const itemJSON = `{
	"verified": false,
	"w": 2,
	"h": 4,
	"icon": "https://web.poecdn.com/gen/image/WzI1LDE0LHsiZiI6IjJESXRlbXMvV2VhcG9ucy9Ud29IYW5kV2VhcG9ucy9Cb3dzL0JvdzQiLCJ3IjoyLCJoIjo0LCJzY2FsZSI6MX1d/d7cd8910cc/Bow4.png",
	"league": "Archnemesis",
	"id": "8ace293cd6606e656802695b7c5cc77954cd7c6f6dc7a13427080a1aa667d20e",
	"sockets": [
		{
			"group": 0,
			"attr": "I",
			"sColour": "B"
		},
		{
			"group": 0,
			"attr": "I",
			"sColour": "B"
		},
		{
			"group": 0,
			"attr": "D",
			"sColour": "G"
		},
		{
			"group": 0,
			"attr": "I",
			"sColour": "B"
		},
		{
			"group": 0,
			"attr": "D",
			"sColour": "G"
		},
		{
			"group": 0,
			"attr": "D",
			"sColour": "G"
		}
	],
	"name": "Rapture Nock",
	"typeLine": "Ranger Bow",
	"baseType": "Ranger Bow",
	"identified": true,
	"ilvl": 83,
	"note": "~price 15 chaos",
	"corrupted": true,
	"properties": [
		{
			"name": "Bow",
			"values": [],
			"displayMode": 0
		},
		{
			"name": "Quality",
			"values": [
				[
					"+11%",
					1
				]
			],
			"displayMode": 0,
			"type": 6
		},
		{
			"name": "Physical Damage",
			"values": [
				[
					"62-130",
					1
				]
			],
			"displayMode": 0,
			"type": 9
		},
		{
			"name": "Elemental Damage",
			"values": [
				[
					"128-227",
					5
				],
				[
					"14-219",
					6
				]
			],
			"displayMode": 0,
			"type": 10
		},
		{
			"name": "Critical Strike Chance",
			"values": [
				[
					"6.00%",
					0
				]
			],
			"displayMode": 0,
			"type": 12
		},
		{
			"name": "Attacks per Second",
			"values": [
				[
					"1.30",
					0
				]
			],
			"displayMode": 0,
			"type": 13
		},
		{
			"name": "Stack Size",
			"values": [
				[
					"1/9",
					0
				]
			],
			"displayMode": 0,
			"type": 32
		}
	],
	"requirements": [
		{
			"name": "Level",
			"values": [
				[
					"60",
					0
				]
			],
			"displayMode": 0
		},
		{
			"name": "Dex",
			"values": [
				[
					"212",
					0
				]
			],
			"displayMode": 1
		}
	],
	"explicitMods": [
		"+1 to Level of Socketed Bow Gems",
		"Adds 128 to 227 Cold Damage",
		"Adds 14 to 219 Lightning Damage",
		"23% increased Stun Duration on Enemies",
		"+463 to Accuracy Rating",
		"Attacks have 20% chance to cause Bleeding",
		"28% increased Damage with Bleeding"
	],
	"frameType": 2,
	"extended": {
		"category": "weapons",
		"subcategories": [
			"bow"
		],
		"prefixes": 3,
		"suffixes": 3
	},
	"x": 10,
	"y": 8,
	"inventoryId": "Stash35",
	"socketedItems": []
}`

const expectedIndexJSON = `{
	"price_value": 15,
	"price_currency": "chaos",
	"socketCount": 6,
	"socketLinks": 6,
	"modCount": {
		"explicit": 7
	},
	"explicitMods": [
		{
			"text": "+# to Level of Socketed Bow Gems",
			"values": [
				1
			]
		},
		{
			"text": "Adds # to # Cold Damage",
			"average": 177.5,
			"values": [
				128,
				227
			]
		},
		{
			"text": "Adds # to # Lightning Damage",
			"average": 116.5,
			"values": [
				14,
				219
			]
		},
		{
			"text": "#% increased Stun Duration on Enemies",
			"values": [
				23
			]
		},
		{
			"text": "+# to Accuracy Rating",
			"values": [
				463
			]
		},
		{
			"text": "Attacks have #% chance to cause Bleeding",
			"values": [
				20
			]
		},
		{
			"text": "#% increased Damage with Bleeding",
			"values": [
				28
			]
		}
	],
	"properties": {
		"attacks_per_second": 1.3,
		"critical_strike_chance": 6,
		"elemental_damage": [
			"128-227",
			"14-219"
		],
		"physical_damage": 96,
		"quality": 11,
		"stack_size": 1
	},
	"requirements": {
		"dex": 212,
		"level": 60
	},
	"ilvl": 83,
	"id": "8ace293cd6606e656802695b7c5cc77954cd7c6f6dc7a13427080a1aa667d20e",
	"name": "Rapture Nock",
	"typeLine": "Ranger Bow",
	"baseType": "Ranger Bow",
	"note": "~price 15 chaos",
	"frameType": 2,
	"x": 10,
	"y": 8,
	"inventoryId": "Stash35",
	"identified": true,
	"corrupted": true,
	"sockets": [
		{
			"group": 0,
			"attr": "I",
			"sColour": "B"
		},
		{
			"group": 0,
			"attr": "I",
			"sColour": "B"
		},
		{
			"group": 0,
			"attr": "D",
			"sColour": "G"
		},
		{
			"group": 0,
			"attr": "I",
			"sColour": "B"
		},
		{
			"group": 0,
			"attr": "D",
			"sColour": "G"
		},
		{
			"group": 0,
			"attr": "D",
			"sColour": "G"
		}
	],
	"extended": {
		"category": "weapons",
		"subcategories": [
			"bow"
		],
		"prefixes": 3,
		"suffixes": 3
	}
}`

func TestParseItem(t *testing.T) {
	var item Item
	require.NoError(t, json.Unmarshal([]byte(itemJSON), &item))

	indexedItem := item.ToIndexedItem()
	bytes, err := json.MarshalIndent(indexedItem, "", "\t")
	require.NoError(t, err)
	require.Equal(t, expectedIndexJSON, string(bytes))
}

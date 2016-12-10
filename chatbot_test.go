package main

import (
	"reflect"
	"testing"
)

func TestParseUnique_PlusOneBelly(t *testing.T) {
	raw := `Rarity: Unique
Belly of the Beast
Full Wyrmscale
--------
Quality: +20% (augmented)
Armour: 541 (augmented)
Evasion Rating: 217 (augmented)
--------
Requirements:
Level: 46
Str: 68 (unmet)
Dex: 68 (unmet)
--------
Sockets: B-B-G-R-G-B
--------
Item Level: 75
--------
+1 to Level of Socketed Gems
--------
179% increased Armour
38% increased maximum Life
+11% to all Elemental Resistances
50% increased Flask Life Recovery rate
Extra gore
--------
There is no safer place
Than the Belly of the Beast
--------
Corrupted`

	expected := &Item{
		Ilvl:      75,
		Corrupted: true,
		FrameType: rarities["Unique"],
		TypeLine:  "Full Wyrmscale",
		Properties: []Property{
			makeProperty("Armour", "541"),
			makeProperty("Evasion Rating", "217"),
			makeProperty("Quality", "20"),
		},
		Requirements: []Property{
			makeProperty("Dex", "68"),
			makeProperty("Level", "46"),
			makeProperty("Str", "68"),
		},
		Sockets: []Socket{
			Socket{0, colors["B"]},
			Socket{0, colors["B"]},
			Socket{0, colors["G"]},
			Socket{0, colors["R"]},
			Socket{0, colors["G"]},
			Socket{0, colors["B"]},
		},
		ImplicitMods: []string{"+1 to Level of Socketed Gems"},
		ExplicitMods: []string{
			"179% increased Armour",
			"38% increased maximum Life",
			"+11% to all Elemental Resistances",
			"50% increased Flask Life Recovery rate",
			"Extra gore",
		},
	}

	item, err := parseClipboardItem(raw)
	if err != nil {
		t.Fatalf("bad: %v", err)
	}

	if !reflect.DeepEqual(item, expected) {
		t.Fatalf("bad: \n%v\n%v", item, expected)
	}
}

func TestParseUnique_RareChest(t *testing.T) {
	raw := `Rarity: Rare
Foe Mantle
Vaal Regalia
--------
Quality: +20% (augmented)
Energy Shield: 411 (augmented)
--------
Requirements:
Level: 68
Int: 194 (unmet)
--------
Sockets: B G R-B B-B
--------
Item Level: 81
--------
115% increased Energy Shield
+23% to Cold Resistance
12% increased Stun and Block Recovery`

	expected := &Item{
		Ilvl:      81,
		FrameType: rarities["Rare"],
		TypeLine:  "Vaal Regalia",
		Properties: []Property{
			makeProperty("Energy Shield", "411"),
			makeProperty("Quality", "20"),
		},
		Requirements: []Property{
			makeProperty("Int", "194"),
			makeProperty("Level", "68"),
		},
		Sockets: []Socket{
			Socket{0, colors["B"]},
			Socket{1, colors["G"]},
			Socket{2, colors["R"]},
			Socket{2, colors["B"]},
			Socket{3, colors["B"]},
			Socket{3, colors["B"]},
		},
		ExplicitMods: []string{
			"115% increased Energy Shield",
			"+23% to Cold Resistance",
			"12% increased Stun and Block Recovery",
		},
	}

	item, err := parseClipboardItem(raw)
	if err != nil {
		t.Fatalf("bad: %v", err)
	}

	if !reflect.DeepEqual(item, expected) {
		t.Fatalf("bad: \n%v\n%v", item, expected)
	}
}

func TestParseUnique_RareBow(t *testing.T) {
	raw := `Rarity: Rare
Fate Thunder
Harbinger Bow
--------
Bow
Quality: +20% (augmented)
Physical Damage: 77-201 (augmented)
Elemental Damage: 34-74 (augmented), 23-38 (augmented)
Critical Strike Chance: 7.70% (augmented)
Attacks per Second: 1.20
--------
Requirements:
Level: 68
Dex: 212 (unmet)
--------
Sockets: G-G G
--------
Item Level: 69
--------
31% increased Critical Strike Chance
--------
101% increased Physical Damage
Adds 34 to 74 Fire Damage
Adds 23 to 38 Cold Damage
23% increased Critical Strike Chance`

	expected := &Item{
		Ilvl:      69,
		FrameType: rarities["Rare"],
		TypeLine:  "Harbinger Bow",
		Properties: []Property{
			makeProperty("Attacks per Second", "1.20"),
			makeProperty("Critical Strike Chance", "7.70"),
			makeProperty("Elemental Damage", "34-74", "23-38"),
			makeProperty("Physical Damage", "77-201"),
			makeProperty("Quality", "20"),
		},
		Requirements: []Property{
			makeProperty("Dex", "212"),
			makeProperty("Level", "68"),
		},
		Sockets: []Socket{
			Socket{0, colors["G"]},
			Socket{0, colors["G"]},
			Socket{1, colors["G"]},
		},
		ImplicitMods: []string{
			"31% increased Critical Strike Chance",
		},
		ExplicitMods: []string{
			"101% increased Physical Damage",
			"Adds 34 to 74 Fire Damage",
			"Adds 23 to 38 Cold Damage",
			"23% increased Critical Strike Chance",
		},
	}

	item, err := parseClipboardItem(raw)
	if err != nil {
		t.Fatalf("bad: %v", err)
	}

	if !reflect.DeepEqual(item, expected) {
		t.Fatalf("bad: \n%v\n%v", item, expected)
	}
}

func TestParseUnique_Tabula(t *testing.T) {
	raw := `Rarity: Unique
Tabula Rasa
Simple Robe
--------
Sockets: W-W-W-W-W-W
--------
Item Level: 17
--------
Corrupted`

	expected := &Item{
		Corrupted: true,
		Ilvl:      17,
		FrameType: rarities["Unique"],
		TypeLine:  "Simple Robe",
		Sockets: []Socket{
			Socket{0, colors["W"]},
			Socket{0, colors["W"]},
			Socket{0, colors["W"]},
			Socket{0, colors["W"]},
			Socket{0, colors["W"]},
			Socket{0, colors["W"]},
		},
		Requirements: []Property{},
		Properties:   []Property{},
	}

	item, err := parseClipboardItem(raw)
	if err != nil {
		t.Fatalf("bad: %v", err)
	}

	if !reflect.DeepEqual(item, expected) {
		t.Fatalf("bad: \n%v\n%v", item, expected)
	}
}

func TestParseItem_Rare(t *testing.T) {
	raw := `Rarity: Rare
Pandemonium Choker
Gold Amulet
--------
Requirements:
Level: 64
--------
Item Level: 81
--------
20% increased Rarity of Items found
--------
Adds 11 to 21 Physical Damage to Attacks
+40% increased Elemental Damage with Weapons
+252 to Accuracy Rating
+63 to maximum Life
+11% increased Rarity of Items found`

	expected := &Item{
		Ilvl:       81,
		FrameType:  rarities["Rare"],
		TypeLine:   "Gold Amulet",
		Properties: []Property{},
		Requirements: []Property{
			makeProperty("Level", "64"),
		},
		ImplicitMods: []string{
			"20% increased Rarity of Items found",
		},
		ExplicitMods: []string{
			"Adds 11 to 21 Physical Damage to Attacks",
			"+40% increased Elemental Damage with Weapons",
			"+252 to Accuracy Rating",
			"+63 to maximum Life",
			"+11% increased Rarity of Items found",
		},
	}

	item, err := parseClipboardItem(raw)
	if err != nil {
		t.Fatalf("bad: %v", err)
	}

	if !reflect.DeepEqual(item, expected) {
		t.Fatalf("bad: \n%v\n%v", item, expected)
	}
}

func TestParseItem_Note(t *testing.T) {
	raw := `Rarity: Rare
Brood Harness
Chain Belt
--------
Requirements:
Level: 52
--------
Item Level: 74
--------
+14 to maximum Energy Shield
--------
34% increased Elemental Damage with Weapons
+39 to Strength
+28 to maximum Energy Shield
+31% to Cold Resistance
13% increased Flask Mana Recovery rate
--------
Note: ~price 3 chaos`

	expected := &Item{
		Ilvl:       74,
		FrameType:  rarities["Rare"],
		TypeLine:   "Chain Belt",
		Properties: []Property{},
		Requirements: []Property{
			makeProperty("Level", "52"),
		},
		ImplicitMods: []string{
			"+14 to maximum Energy Shield",
		},
		ExplicitMods: []string{
			"34% increased Elemental Damage with Weapons",
			"+39 to Strength",
			"+28 to maximum Energy Shield",
			"+31% to Cold Resistance",
			"13% increased Flask Mana Recovery rate",
		},
	}

	item, err := parseClipboardItem(raw)
	if err != nil {
		t.Fatalf("bad: %v", err)
	}

	if !reflect.DeepEqual(item, expected) {
		t.Fatalf("bad: \n%v\n%v", item, expected)
	}
}

func TestUniqueJewel(t *testing.T) {
	raw := `Rarity: Unique
Fluid Motion
Viridian Jewel
--------
Radius: Large
--------
Item Level: 76
--------
+22 to Dexterity
Strength from Passives in Radius is Transformed to Dexterity
--------
Even the strongest of steel can be made to bend.
--------
Place into an allocated Jewel Socket on the Passive Skill Tree. Right click to remove from the Socket.
--------
Corrupted`

	expected := &Item{
		Ilvl:      76,
		Corrupted: true,
		FrameType: rarities["Unique"],
		TypeLine:  "Viridian Jewel",
		Properties: []Property{
			makeProperty("Radius", "Large"),
		},
		Requirements: []Property{},
		ExplicitMods: []string{
			"+22 to Dexterity",
			"Strength from Passives in Radius is Transformed to Dexterity",
		},
	}

	item, err := parseClipboardItem(raw)
	if err != nil {
		t.Fatalf("bad: %v", err)
	}

	if !reflect.DeepEqual(item, expected) {
		t.Fatalf("bad: \n%v\n%v", item, expected)
	}
}

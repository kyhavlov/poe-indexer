package main

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"net/http"
	"regexp"
	"strconv"
	"strings"
	"time"
)

var floatExpr = regexp.MustCompile(`-?\d[\d,]*[\.]?[\d{2}]*`)
var rangeExpr = regexp.MustCompile(`\d+-\d+`)

type Item struct {
	// Raw fields from stash api
	EnchantMods   []string `json:"enchantMods,omitempty"`
	ImplicitMods  []string `json:"implicitMods,omitempty"`
	FracturedMods []string `json:"fracturedMods,omitempty"`
	ExplicitMods  []string `json:"explicitMods,omitempty"`
	CraftedMods   []string `json:"craftedMods,omitempty"`
	VeiledMods    []string `json:"veiledMods,omitempty"`
	UtilityMods   []string `json:"utilityMods,omitempty"`

	AdditionalProperties  Properties `json:"additionalProperties,omitempty"`
	NotableProperties     Properties `json:"notableProperties,omitempty"`
	Properties            Properties `json:"properties,omitempty"`
	Requirements          Properties `json:"requirements,omitempty"`
	NextLevelRequirements Properties `json:"nextLevelRequirements,omitempty"`

	ItemCommon
}

func (i *Item) ToIndexedItem() *IndexedItem {
	out := &IndexedItem{
		ItemCommon: i.ItemCommon,
	}

	// Pull out price data
	matches := priceString.FindStringSubmatch(i.Note)
	if matches == nil {
		matches = priceString.FindStringSubmatch(i.InventoryID)
	}
	if matches != nil && len(matches) > 2 {
		value, err := strconv.ParseFloat(matches[1], 64)
		if err == nil {
			out.PriceValue = JSONFloat(value)
			out.PriceCurrency = matches[2]
		} else if strings.Contains(matches[1], "/") {
			parts := strings.SplitN(matches[1], "/", 2)
			a, _ := strconv.ParseFloat(parts[0], 64)
			b, _ := strconv.ParseFloat(parts[1], 64)
			if b != 0 {
				out.PriceValue = JSONFloat(a / b)
				out.PriceCurrency = matches[2]
			}
		}
	}

	// Calculate socket links
	groupCounts := make(map[int]int)
	for _, socket := range i.Sockets {
		groupCounts[socket.Group]++
	}
	for _, count := range groupCounts {
		if count > out.SocketCount {
			out.SocketLinks = count
		}
	}
	out.SocketCount = len(i.Sockets)

	// Reformat mod lists
	formatMods := func(mods []string) []Modifier {
		out := make([]Modifier, 0, len(mods))
		for _, mod := range mods {
			submatchall := floatExpr.FindAllString(mod, -1)
			newMod := mod

			var average *float64
			var values []JSONDouble
			for _, element := range submatchall {
				newMod = strings.Replace(newMod, element, "#", 1)
				value, _ := strconv.ParseFloat(element, 64)
				if average == nil {
					average = &value
				} else {
					*average += value
				}
				values = append(values, JSONDouble(value))
			}
			if average != nil {
				*average /= float64(len(values))
			}

			modifier := Modifier{
				Text:   newMod,
				Values: values,
			}
			if len(values) > 1 {
				avg := JSONDouble(*average)
				modifier.Average = &avg
			}
			out = append(out, modifier)
		}
		return out
	}

	out.EnchantMods = formatMods(i.EnchantMods)
	out.ImplicitMods = formatMods(i.ImplicitMods)
	out.FracturedMods = formatMods(i.FracturedMods)
	out.ExplicitMods = formatMods(i.ExplicitMods)
	out.CraftedMods = formatMods(i.CraftedMods)
	out.VeiledMods = formatMods(i.VeiledMods)
	out.UtilityMods = formatMods(i.UtilityMods)

	out.ModCount.Enchant = len(out.EnchantMods)
	out.ModCount.Implicit = len(out.ImplicitMods)
	out.ModCount.Fractured = len(out.FracturedMods)
	out.ModCount.Explicit = len(out.ExplicitMods)
	out.ModCount.Crafted = len(out.CraftedMods)
	out.ModCount.Veiled = len(out.VeiledMods)
	out.ModCount.Utility = len(out.UtilityMods)

	flattenProperties := func(props Properties) map[string]interface{} {
		out := make(map[string]interface{})
		for _, prop := range props {
			if strings.Contains(prop.Name, ",") {
				continue
			}
			sanitizedName := strings.ToLower(strings.Replace(prop.Name, " ", "_", -1))
			if sanitizedName == "" {
				if len(prop.Values) == 1 && len(prop.Values[0]) == 1 {
					out[prop.Values[0][0]] = ""
					continue
				}
			}

			if len(prop.Values) == 1 && len(prop.Values[0]) == 1 {
				out[sanitizedName] = prop.Values[0][0]
				isRange := false
				if rangeExpr.MatchString(prop.Values[0][0]) {
					isRange = true
					prop.Values[0][0] = strings.Replace(prop.Values[0][0], "-", " ", 1)
				}
				parsedVals := floatExpr.FindAllString(prop.Values[0][0], -1)

				var average float64
				valCount := 0
				for _, element := range parsedVals {
					value, _ := strconv.ParseFloat(element, 64)
					if valCount == 0 {
						average = value
					} else {
						average += value
					}
					valCount++
					if !isRange {
						break
					}
				}
				if valCount > 0 {
					average /= float64(valCount)
					out[sanitizedName] = JSONFloat(average)
				}
			}

			if len(prop.Values) > 1 {
				values := make([]string, 0)
				for _, val := range prop.Values {
					values = append(values, val[0])
				}
				out[sanitizedName] = values
			}
		}
		return out
	}

	out.AdditionalProperties = flattenProperties(i.AdditionalProperties)
	out.NotableProperties = flattenProperties(i.NotableProperties)
	out.Properties = flattenProperties(i.Properties)
	out.Requirements = flattenProperties(i.Requirements)
	out.NextLevelRequirements = flattenProperties(i.NextLevelRequirements)

	return out
}

type IndexedItem struct {
	// Derived metadata fields
	Account     string `json:"account,omitempty"`
	StashID     string `json:"stashId,omitempty"`
	CreatedAt   string `json:"created_at,omitempty"`
	LastUpdated string `json:"last_updated,omitempty"`
	create      bool   `json:"-"`

	PriceValue    JSONFloat `json:"price_value,omitempty"`
	PriceCurrency string    `json:"price_currency,omitempty"`

	SocketCount int `json:"socketCount,omitempty"`
	SocketLinks int `json:"socketLinks,omitempty"`

	ModCount ModCounts `json:"modCount,omitempty"`

	// Formatted fields
	EnchantMods   []Modifier `json:"enchantMods,omitempty"`
	ImplicitMods  []Modifier `json:"implicitMods,omitempty"`
	FracturedMods []Modifier `json:"fracturedMods,omitempty"`
	ExplicitMods  []Modifier `json:"explicitMods,omitempty"`
	CraftedMods   []Modifier `json:"craftedMods,omitempty"`
	VeiledMods    []Modifier `json:"veiledMods,omitempty"`
	UtilityMods   []Modifier `json:"utilityMods,omitempty"`

	AdditionalProperties  map[string]interface{} `json:"additionalProperties,omitempty"`
	NotableProperties     map[string]interface{} `json:"notableProperties,omitempty"`
	Properties            map[string]interface{} `json:"properties,omitempty"`
	Requirements          map[string]interface{} `json:"requirements,omitempty"`
	NextLevelRequirements map[string]interface{} `json:"nextLevelRequirements,omitempty"`

	ItemCommon
}

type ModCounts struct {
	Enchant   int `json:"enchant,omitempty"`
	Implicit  int `json:"implicit,omitempty"`
	Fractured int `json:"fractured,omitempty"`
	Explicit  int `json:"explicit,omitempty"`
	Crafted   int `json:"crafted,omitempty"`
	Veiled    int `json:"veiled,omitempty"`
	Utility   int `json:"utility,omitempty"`
}

type Modifier struct {
	Text    string       `json:"text"`
	Average *JSONDouble  `json:"average,omitempty"`
	Values  []JSONDouble `json:"values,omitempty"`
}

type ItemCommon struct {
	Verified          bool   `json:"verified,omitempty"`
	Ilvl              int    `json:"ilvl,omitempty"`
	Support           bool   `json:"support,omitempty"`
	ID                string `json:"id,omitempty"`
	Name              string `json:"name,omitempty"`
	TypeLine          string `json:"typeLine,omitempty"`
	BaseType          string `json:"baseType,omitempty"`
	LockedToCharacter bool   `json:"lockedToCharacter,omitempty"`
	Note              string `json:"note,omitempty"`
	FrameType         int    `json:"frameType,omitempty"`
	X                 int    `json:"x,omitempty"`
	Y                 int    `json:"y,omitempty"`
	InventoryID       string `json:"inventoryId,omitempty"`
	TalismanTier      int    `json:"talismanTier,omitempty"`
	AbyssJewel        bool   `json:"abyssJewel,omitempty"`
	StackSize         int    `json:"stackSize,omitempty"`
	MaxStackSize      int    `json:"maxStackSize,omitempty"`

	Identified  bool            `json:"identified,omitempty"`
	Corrupted   bool            `json:"corrupted,omitempty"`
	Duplicated  bool            `json:"duplicated,omitempty"`
	Split       bool            `json:"split,omitempty"`
	Elder       bool            `json:"elder,omitempty"`
	Shaper      bool            `json:"shaper,omitempty"`
	Searing     bool            `json:"searing,omitempty"`
	Tangled     bool            `json:"tangled,omitempty"`
	Synthesised bool            `json:"synthesised,omitempty"`
	Fractured   bool            `json:"fractured,omitempty"`
	Influences  map[string]bool `json:"influences,omitempty"`

	Sockets  []Socket `json:"sockets,omitempty"`
	Extended Extended `json:"extended,omitempty"`
}

type JSONDouble float64

func (d JSONDouble) MarshalJSON() ([]byte, error) {
	str := fmt.Sprintf("%v\n", d)
	idx := strings.Index(str, ".")
	if idx != -1 {
		str = str[:idx+3]
	}

	return []byte(str), nil
}

type JSONFloat float64

func (f JSONFloat) MarshalJSON() ([]byte, error) {
	str := fmt.Sprintf("%v\n", f)
	idx := strings.Index(str, ".")
	if idx != -1 {
		end := idx + 5
		if len(str) < end {
			end = len(str)
		}
		str = str[:end]
		// Remove trailing deimcal zeros
		for strings.HasSuffix(str, "0") {
			if strings.HasSuffix(str, ".0") {
				break
			}
			str = str[:len(str)-1]
		}
	}

	return []byte(str), nil
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
	AccountName       string         `json:"accountName"`
	LastCharacterName string         `json:"lastCharacterName"`
	ID                string         `json:"id"`
	Stash             string         `json:"stash"`
	StashType         string         `json:"stashType"`
	Items             []*Item        `json:"items"`
	ItemIDs           []string       `json:"-"`
	FormattedItems    []*IndexedItem `json:"-"`
	Public            bool           `json:"public"`
	League            string         `json:"league"`
}

func getNextStashes(client *http.Client, currentID string) (*APIResponse, error) {
	start := time.Now()
	req, err := http.NewRequest("GET", "http://api.pathofexile.com/public-stash-tabs?id="+currentID, nil)
	if err != nil {
		fmt.Printf("Error creating request: %v\n", err)
		return nil, err
	}

	response, err := client.Do(req)
	if err != nil {
		response.Body.Close()
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

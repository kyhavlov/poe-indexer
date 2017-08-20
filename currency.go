package main

import (
	"log"
	"net/http"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"time"
)

const apiUrl = "poe.ninja/api/Data/GetCurrencyOverview?league=Harbinger"

type CurrencyInfo struct {
	Lines []struct {
		CurrencyTypeName string  `json:"currencyTypeName"`
		ChaosEquivalent  float64 `json:"chaosEquivalent"`
	}
}

type CurrencyTracker struct {
	currencyValues map[string]float64
	sync.RWMutex
}

func NewCurrencyTracker() *CurrencyTracker {
	return &CurrencyTracker{
		currencyValues: map[string]float64{
			"Chaos Orb": 1.0,
		},
	}
}

func (c *CurrencyTracker) TrackCurrencyValues() {
	for {
		err := c.fetchCurrencyInfo()
		if err != nil {
			log.Printf("Error fetching currency info: %v", err)
		}
		time.Sleep(time.Hour)
	}
}

func (c *CurrencyTracker) fetchCurrencyInfo() error {
	info := CurrencyInfo{}
	err := doRequest(&http.Client{}, "GET", apiUrl, nil, &info)
	if err != nil {
		return err
	}
	c.Lock()
	defer c.Unlock()
	for _, line := range info.Lines {
		c.currencyValues[line.CurrencyTypeName] = line.ChaosEquivalent
	}
	log.Printf("Fetched current currency rates, latest exalt value: %0.2f", c.currencyValues[EXALTED])
	return nil
}

var buyoutFormat = regexp.MustCompile("\\S+ (\\d+(?:\\.\\d+)?) (\\w+)")

// parseBuyout takes a buyout string, such as "~price 1.2 exa" and returns a buyout
// converted to chaos orb value.
func (c *CurrencyTracker) ParseBuyout(raw string) float64 {
	buyout := buyoutFormat.FindStringSubmatch(strings.ToLower(raw))
	if len(buyout) < 3 {
		return -1.0
	}
	currency, ok := aliasMap[buyout[2]]
	if !ok {
		return -1.0
	}
	if currencyValue, ok := c.currencyValues[currency]; ok {
		chaosEquiv, err := strconv.ParseFloat(buyout[1], 64)
		if err != nil {
			return -1.0
		}
		return chaosEquiv * currencyValue
	} else {
		return -1.0
	}
}

const CHAOS = "Chaos Orb"
const EXALTED = "Exalted Orb"
const VAAL = "Vaal Orb"
const REGRET = "Orb of Regret"
const CHANCE = "Orb of Chance"
const DIVINE = "Divine Orb"
const ALTERATION = "Orb of Alteration"
const ALCHEMY = "Orb of Alchemy"
const FUSING = "Orb of Fusing"
const JEWELLER = "Jeweller's Orb"
const GCP = "Gemcutter's Prism"
const BLESSED = "Blessed Orb"

var aliasMap = map[string]string{
	"chaos":       CHAOS,
	"chaoss":      CHAOS,
	"chaosgg":     CHAOS,
	"choas":       CHAOS,
	"chaos3":      CHAOS,
	"chas":        CHAOS,
	"chaos_crab3": CHAOS,
	"chaos1":      CHAOS,
	"chaos2":      CHAOS,
	"c":           CHAOS,
	"vaal":        VAAL,
	"regret":      REGRET,
	"exa":         EXALTED,
	"exalted":     EXALTED,
	"exalteds":    EXALTED,
	"ex":          EXALTED,
	"exalt":       EXALTED,
	"exalts":      EXALTED,
	"chance":      CHANCE,
	"divine":      DIVINE,
	"alt":         ALTERATION,
	"alts":        ALTERATION,
	"altQ":        ALTERATION,
	"alteration":  ALTERATION,
	"alch":        ALCHEMY,
	"alch2":       ALCHEMY,
	"alch3":       ALCHEMY,
	"alchemy":     ALCHEMY,
	"alc":         ALCHEMY,
	"chisel":      "Cartographer's Chisel",
	"fuse":        FUSING,
	"fusing":      FUSING,
	"fus":         FUSING,
	"jew":         JEWELLER,
	"jewellers":   JEWELLER,
	"scour":       "Orb of Scouring",
	"regal":       "Regal Orb",
	"chrom":       "Chromatic Orb",
	"gcp":         GCP,
	"pris":        GCP,
	"blessed":     BLESSED,
	"bless":       BLESSED,
}

# AstraBridge Edge Primitives

Last updated: 2026-07-03

## Purpose

This document defines the first reusable edge-language primitives for AstraBridge.

The goal is to move the product away from generic rounded cards and toward a restrained Starbridge frame language:

- silver-blue edge lines instead of heavy dark borders
- shallow inner sheen instead of thick glass
- lightweight row and tab activation instead of oversized pills
- a semantic lower-corner constellation accent for permissive surfaces

## Primitive Set

### 1. Surface frame

Used for shell-level containers such as settings layouts and guard surfaces.

Characteristics:

- thin silver-blue border
- cool white panel fill
- top-edge sheen
- shallow shadow only when needed
- clipped lower-corner accent zone

Current classes/selectors:

- `starbridge-surface-frame`
- `starbridge-surface-panel`

### 2. Control edge

Used for buttons, inputs, textareas, and selects.

Characteristics:

- slightly brighter silver line than the default border
- subtle vertical fill gradient
- focus ring based on cool blue glow instead of thick dark outlines
- hover state strengthens the edge before it strengthens the fill

### 3. Row and tab edge

Used for navigation rows, segmented controls, and settings nav items.

Characteristics:

- transparent resting edge
- hover adds a quiet silver border
- active state uses a light silver-blue fill plus a precise edge highlight
- no heavy badge-like capsule treatment

### 4. Corner constellation accent

Used only on surfaces that can tolerate stronger brand presence:

- settings content
- launch-isolation / guard surfaces

Current semantic motif:

- a stylized `Orion` constellation
- shoulder stars
- three-star belt
- two lower stars
- descending sword

This motif is meant to read as a recognizable real constellation first, then as routing, handoff, and bridge continuity, rather than as random decorative geometry.

### 5. Composer star track

Used on the main task composer only.

Characteristics:

- the composer border becomes a quiet lower-edge track rather than a decorated card
- the track sits on the bottom and lower-right, leaving the reading band and typing band clear
- a slow silver-blue traveler can stay faintly visible at rest
- focus, sending, recording, and drop states strengthen the same track instead of introducing new chrome
- error state warms the track rather than adding a second large warning frame

This primitive is meant to make the composer feel like a live route surface without turning the input box into an illustration.

## Motion Rules

The corner constellation uses four restrained motion layers:

1. silver base links that stay visible even when motion is off
2. directional glow that runs along those links
3. moving lit stars that read as relay handoff rather than random particles
4. short-lived dust trail attached to the moving stars

The composer star track uses a lighter version of the same logic:

1. a static silver rail
2. a moving dash/glow along the rail
3. a single traveler star
4. a very short dust tail

Rules:

- motion must stay in the corner and never compete with form fields or body copy
- main task surfaces should not use this stronger accent by default
- reduced-motion must drop the moving trace and travelers, keeping only the static constellation
- reduced-motion must also drop the composer traveler and running dash, keeping only the static rail and nodes
- avoid filled oval plates or decorative blobs under the motif; the structure should read as stars and links, not as a badge

## Constraints

1. Edge primitives should increase structure, not card density.
2. Brightness should come from silver-white highlights, not saturated blue fills.
3. Corner accents should sit in a lower corner, never through the main reading band.
4. The semantic constellation should remain identifiable even when motion is disabled.
5. Future surfaces may reuse the same primitive, but they should tune opacity rather than invent a new motif.

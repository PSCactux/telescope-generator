# Refractor 70/400

## Optics

- Effective aperture 66.0 mm (lens 70 mm), focal length 400 mm, f/6.06
- Dawes limit 1.76", Rayleigh limit 2.1"
- Useful magnification 9.4x to 132x, limiting magnitude ~11.6
- Light grasp ~89x the naked eye
- Note: the cell openings stop the lens down from 70 to 66.0 mm; reduce objective.shelf_width to recover aperture

| Eyepiece | Magnification | Exit pupil | True field |
|---:|---:|---:|---:|
| 20 mm | 20.0x | 3.3 mm | 2.5 deg |
| 10 mm | 40.0x | 1.65 mm | 1.25 deg |
| 9 mm | 44.4x | 1.49 mm | 1.01 deg |

## Focus

Tube segments: 200, 136 mm. With the 16 mm spacer the nominal focus sits inside the focuser travel (9.25 mm towards the objective, 8.75 mm away). Other spacer combinations reach from -58.8 to +25.2 mm around the nominal focus.

Focus test before printing the tubes: with the cell and the eyepiece holder only, the eyepiece shoulder should be about 375.2 mm behind the rear face of the cell when a distant object is sharp. If you measure something else, put the difference into objective.focal_length and rebuild.

## Parts

| Part | Qty | Size (mm) | Description |
|---|---:|---|---|
| lens_cell | 1 | 88 x 88 x 52 | lens cell, glass pocket 72.25 x 17.0 mm, female T at the rear |
| lens_retainer | 1 | 76.5 x 76.5 x 13 | threaded retainer ring; use a soft ring between it and the glass |
| tube_1 | 1 | 88 x 88 x 200 | tube segment 1 (200 mm), counted from the objective |
| tube_2 | 1 | 88 x 88 x 136 | tube segment 2 (136 mm), counted from the objective |
| spacer_16 | 1 | 88 x 88 x 28 | focus spacer, net extension 16 mm |
| spacer_20 | 1 | 88 x 88 x 32 | focus spacer, net extension 20 mm |
| spacer_30 | 1 | 88 x 88 x 42 | focus spacer, net extension 30 mm |
| focuser_cap | 1 | 88 x 88 x 35 | rear cap: female F (focuser) below, male T above |
| eyepiece_holder | 1 | 55.8 x 55.8 x 45 | helical focuser, bore 31.90, travel 18 mm |
| eyepiece_screw | 1 | 15.7 x 15.7 x 23 | printed thumb screw that holds the eyepiece |
| eyepiece_nut_c25 | 1 | 14 x 12 x 8 | printed nut for the thumb screw |
| eyepiece_nut_c35 | 1 | 14 x 12 x 8 | looser spare nut (grooved) |
| mount_cradle | 1 | 136 x 45 x 58.2 | tube cradle with tripod foot (printed 1/4"-20 thread) |
| mount_clamp | 1 | 136 x 49.2 x 45 | upper half ring of the mount |
| mount_screw | 2 | 15.7 x 15.7 x 37 | printed screws that close the mount |
| mount_nut_c25 | 2 | 14 x 12 x 8 | printed nuts for the mount, slide into the cradle ears |
| dew_shield | 1 | 93.3 x 93.3 x 100 | dew shield, 100 mm |
| dust_cap | 1 | 97.8 x 97.8 x 12 | slip-on dust cap |

## Plates

- `plate_01.stl` (200.0 mm tall): tube_1
- `plate_02.stl` (136.0 mm tall): tube_2
- `plate_03.stl` (100.0 mm tall): dew_shield, lens_cell, mount_cradle, spacer_20, mount_screw#1, mount_screw#2, eyepiece_screw, eyepiece_nut_c25, eyepiece_nut_c35, mount_nut_c25#1, mount_nut_c25#2
- `plate_04.stl` (45.0 mm tall): spacer_30, focuser_cap, mount_clamp, eyepiece_holder, lens_retainer
- `plate_05.stl` (28.0 mm tall): dust_cap, spacer_16

## Checks

- [x] cell bore = gauge fit or measured + 2 x clearance (72.25 mm)
- [x] glass pocket deeper than the edge thickness (17.0 >= 15.5 + 1)
- [x] retainer nose fits in the pocket (72.00 < 72.05)
- [x] ledge supports the glass edge (aperture 67.00)
- [x] retainer thread engaged with 14.0 mm of glass (12.0 mm)
- [x] retainer thread engaged with 17.0 mm of glass (9.0 mm)
- [x] cell wall outside the female T thread >= 1.5 mm (2.75 mm)
- [x] eyepiece bore larger than the barrel (31.90 > 31.75)
- [x] guide shorter than the barrel (eyepiece rests on its shoulder) (18.0 < 20)
- [x] printed nut fits in the holder flange (27.50 <= 28.00)
- [x] holder thread passes through the cap (45.20 > 44.00)
- [x] cap cone is taller than its F ring (23.0 > 14.0)
- [x] focus travel covers the focal plane with the nominal spacer (9.25 mm towards the objective, 8.75 mm away)
- [x] light beam clears the focuser cap opening (opening 45.2 vs beam 32.0)
- [x] tube segment 1 printable (200 mm)
- [x] tube segment 2 printable (136 mm)
- [x] support gusset above the bed (6.2)
- [x] dew shield long enough for its sleeve and stop (100 >= 32.0)

Never point a telescope at the Sun without a certified solar filter.

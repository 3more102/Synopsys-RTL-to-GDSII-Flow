set outdir "ci_ptat/physical/out"
file mkdir $outdir
puts "PTAT_PHYSICAL_PROBE_START"
puts "magic_version=[version]"
puts "tech=[tech name]"

magic::netlist_to_layout "ci_ptat/physical/ptat_core.spice" sky130
load ptat_core
units microns

# Explicitly separate PCells.  magic::netlist_to_layout is a seeding utility,
# not an analog placer.
foreach {inst x y} {
    XMPREF 0um 20um
    XMP_SMALL 10um 20um
    XMP_LARGE 20um 20um
    XMN_SMALL 10um 0um
    XMN_LARGE 20um 0um
} {
    select clear
    select cell $inst
    move to $x $y
}
select clear
select top cell
expand

# Route VGS_SMALL on metal2.
box 11.83um 20.94um 12.13um 21.24um
sky130::via1_draw
box 11.33um 0.90um 11.63um 1.20um
sky130::via1_draw
box 10.83um 0.46um 11.13um 0.76um
sky130::via1_draw
box 12.35um 0.46um 12.65um 21.24um
paint m2
box 11.83um 20.94um 12.65um 21.24um
paint m2
box 11.33um 0.90um 12.65um 1.20um
paint m2
box 10.83um 0.46um 12.65um 0.76um
paint m2
box 12.35um 10.00um 12.65um 10.30um
label VGS_SMALL FreeSans 1 0 0 0 c m2

# Route VGS_LARGE on metal2.
box 21.83um 20.94um 22.13um 21.24um
sky130::via1_draw
box 21.33um 0.90um 21.63um 1.20um
sky130::via1_draw
box 20.83um 0.46um 21.13um 0.76um
sky130::via1_draw
box 22.35um 0.46um 22.65um 21.24um
paint m2
box 21.83um 20.94um 22.65um 21.24um
paint m2
box 21.33um 0.90um 22.65um 1.20um
paint m2
box 20.83um 0.46um 22.65um 0.76um
paint m2
box 22.35um 10.00um 22.65um 10.30um
label VGS_LARGE FreeSans 1 0 0 0 c m2

# PREF: local metal1 terminals -> metal2 stubs -> metal3 horizontal bus.
foreach {x1 y1 x2 y2} {
    1.83um 20.94um 2.13um 21.24um
    0.83um 20.46um 1.13um 20.76um
    10.83um 20.46um 11.13um 20.76um
    20.83um 20.46um 21.13um 20.76um
} {
    box $x1 $y1 $x2 $y2
    sky130::via1_draw
}
foreach {x1 y1 x2 y2} {
    1.83um 18.35um 2.13um 21.24um
    0.83um 18.35um 1.13um 20.76um
    10.83um 18.35um 11.13um 20.76um
    20.83um 18.35um 21.13um 20.76um
} {
    box $x1 $y1 $x2 $y2
    paint m2
}
foreach x {0.98um 1.98um 10.98um 20.98um} {
    # Tcl arithmetic is avoided: use switch for explicit 0.30um via2 boxes.
    switch -- $x {
        0.98um {box 0.83um 18.35um 1.13um 18.65um}
        1.98um {box 1.83um 18.35um 2.13um 18.65um}
        10.98um {box 10.83um 18.35um 11.13um 18.65um}
        20.98um {box 20.83um 18.35um 21.13um 18.65um}
    }
    sky130::via2_draw
}
box 0.75um 18.35um 21.25um 18.65um
paint m3
label PREF FreeSans 1 0 0 0 c m3

# VDD: source terminals -> metal3 rail above the PMOS row.
foreach {x1 x2} {
    0.54um 0.84um
    10.54um 10.84um
    20.54um 20.84um
} {
    box $x1 20.94um $x2 21.24um
    sky130::via1_draw
    box $x1 20.94um $x2 24.65um
    paint m2
    box $x1 24.35um $x2 24.65um
    sky130::via2_draw
}
box 0.40um 24.35um 21.00um 24.65um
paint m3
label VDD FreeSans 1 0 0 0 c m3

# GND: NMOS source terminals -> metal3 rail below the NMOS row.
foreach {x1 x2} {
    10.54um 10.84um
    20.54um 20.84um
} {
    box $x1 0.90um $x2 1.20um
    sky130::via1_draw
    box $x1 -2.15um $x2 1.20um
    paint m2
    box $x1 -2.15um $x2 -1.85um
    sky130::via2_draw
}
box 9.00um -2.15um 21.00um -1.85um
paint m3
label GND FreeSans 1 0 0 0 c m3

# Add a substrate contact tied into GND.
box 7.00um -2.10um 7.40um -1.70um
sky130::subconn_draw
box 7.08um -2.02um 7.32um -1.78um
sky130::mcon_draw
box 7.05um -2.05um 7.35um -1.75um
sky130::via1_draw
box 7.05um -2.15um 9.20um -1.85um
paint m2
box 7.05um -2.15um 7.35um -1.85um
sky130::via2_draw
box 7.05um -2.15um 9.20um -1.85um
paint m3

# Join the PMOS wells physically.  Body-tie refinement follows LVS feedback.
box -1.80um 16.50um 23.50um 26.20um
paint nwell

select clear
select top cell
expand
drc check
set drcresult [drc listall why]
set drccount 0
foreach {errtype coordlist} $drcresult {
    incr drccount [llength $coordlist]
}
set fdrc [open "$outdir/drc_report.txt" w]
puts $fdrc "drc_count=$drccount"
foreach {errtype coordlist} $drcresult {
    puts $fdrc $errtype
    foreach coord $coordlist {puts $fdrc "  $coord"}
}
close $fdrc

save ptat_core_routed
file copy -force ptat_core_routed.mag "$outdir/ptat_core_routed.mag"
gds write "$outdir/ptat_core_routed.gds"
extract all
ext2spice lvs
ext2spice cthresh infinite
ext2spice rthresh infinite
ext2spice -o "$outdir/ptat_core_extracted.spice"

set fmeta [open "$outdir/physical_status.txt" w]
puts $fmeta "magic=[version]"
puts $fmeta "technology=[tech name]"
puts $fmeta "drc_count=$drccount"
puts $fmeta "routing_status=CONNECTED_ATTEMPT"
close $fmeta
puts "PTAT_DRC_COUNT=$drccount"
puts "PTAT_PHYSICAL_PROBE_DONE"
quit -noprompt

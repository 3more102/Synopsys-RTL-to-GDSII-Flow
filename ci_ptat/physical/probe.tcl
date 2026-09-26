set outdir "ci_ptat/physical/out"
file mkdir $outdir
puts "PTAT_PHYSICAL_PROBE_START"
puts "magic_version=[version]"
puts "tech=[tech name]"
magic::netlist_to_layout "ci_ptat/physical/ptat_core.spice" sky130
load ptat_core
# The toolkit seeds devices end-to-end with a small overlap.  Move each
# instance to a deliberately separated floorplan before any DRC/extraction.
units microns
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
set fgeo [open "$outdir/terminal_geometry.txt" w]
foreach {name x1 y1 x2 y2} {
    XMPREF_D 1.88um 20.99um 2.08um 21.19um
    XMPREF_G 0.88um 20.50um 1.08um 20.72um
    XMPREF_S 0.59um 20.99um 0.79um 21.19um
    XMP_SMALL_D 11.88um 20.99um 12.08um 21.19um
    XMP_SMALL_G 10.88um 20.50um 11.08um 20.72um
    XMP_SMALL_S 10.59um 20.99um 10.79um 21.19um
    XMN_SMALL_D 11.38um 0.95um 11.58um 1.15um
    XMN_SMALL_G 10.88um 0.50um 11.08um 0.72um
    XMN_SMALL_S 10.59um 0.95um 10.79um 1.15um
    XMP_LARGE_D 21.88um 20.99um 22.08um 21.19um
    XMP_LARGE_G 20.88um 20.50um 21.08um 20.72um
    XMP_LARGE_S 20.59um 20.99um 20.79um 21.19um
    XMN_LARGE_D 21.38um 0.95um 21.58um 1.15um
    XMN_LARGE_G 20.88um 0.50um 21.08um 0.72um
    XMN_LARGE_S 20.59um 0.95um 20.79um 1.15um
} {
    box $x1 $y1 $x2 $y2
    select clear
    select area
    puts $fgeo "$name [what -listall]"
}
select clear
close $fgeo
select top cell
expand
puts "top_cell=[cellname list self]"
puts "children=[cellname list children ptat_core]"
set fout [open "$outdir/instance_ports.txt" w]
puts $fout "top_cell=[cellname list self]"
foreach child [cellname list children ptat_core] {
    puts $fout "child=$child flags=[cellname flags $child]"
    load $child
    puts $fout "  cell=$child"
    for {set p [port first]} {$p >= 0} {set p [port $p next]} {
        puts $fout "  port $p name=[port $p name] class=[port $p class] use=[port $p use]"
    }
}
close $fout
load ptat_core
select top cell
expand
save "$outdir/ptat_core_autogen"
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
    foreach coord $coordlist { puts $fdrc "  $coord" }
}
close $fdrc
gds write "$outdir/ptat_core_autogen.gds"
extract all
ext2spice lvs
ext2spice cthresh infinite
ext2spice rthresh infinite
ext2spice -o "$outdir/ptat_core_extracted.spice"
puts "PTAT_DRC_COUNT=$drccount"
puts "PTAT_PHYSICAL_PROBE_DONE"
quit -noprompt

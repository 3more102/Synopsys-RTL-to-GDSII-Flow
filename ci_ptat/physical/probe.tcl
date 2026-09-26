set outdir "ci_ptat/physical/out"
file mkdir $outdir
puts "PTAT_PHYSICAL_PROBE_START"
puts "magic_version=[version]"
puts "tech=[tech name]"
magic::netlist_to_layout "ci_ptat/physical/ptat_core.spice" sky130
load ptat_core
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
set drccount [drc list count]
set fdrc [open "$outdir/drc_report.txt" w]
puts $fdrc "drc_count=$drccount"
set drcresult [drc listall why]
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

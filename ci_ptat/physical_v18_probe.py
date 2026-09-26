from __future__ import annotations
import hashlib, json, os, subprocess
from datetime import datetime, timezone
from pathlib import Path

from glayout.flow.pdk.sky130_mapped import sky130_mapped_pdk as sky130
from glayout.flow.primitives.fet import nmos, pmos

OUT = Path(os.environ.get("PTAT_PHYSICAL_OUT", "physical_v18_results")).resolve()
OUT.mkdir(parents=True, exist_ok=True)

def sha256(p: Path) -> str:
    h=hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda:f.read(1<<20), b""): h.update(chunk)
    return h.hexdigest()

def version(cmd):
    p=subprocess.run(cmd, shell=True, text=True, capture_output=True)
    return {"command":cmd,"returncode":p.returncode,"stdout":p.stdout.strip(),"stderr":p.stderr.strip()}

def run_one(name, comp, expected):
    comp.name=name
    gds=OUT/f"{name}.gds"
    cdl=OUT/f"{name}.cdl"
    drc=OUT/f"{name}_drc.rpt"
    lvs=OUT/f"{name}_lvs.rpt"
    comp.write_gds(str(gds))
    cdl.write_text(comp.info["netlist"].generate_netlist(with_pins=True), encoding="utf-8")
    drc_result=sky130.drc_magic(gds, name, output_file=drc)
    lvs_result=sky130.lvs_netgen(gds, name, netlist=cdl, output_file_path=lvs, copy_intermediate_files=True)
    drc_text=drc.read_text(errors="replace")
    lvs_text=lvs.read_text(errors="replace")
    drc_clean=("count: 0" in drc_text and drc_result.get("subproc_code")==0)
    lvs_match=(lvs_result.get("magic_subproc_code")==0 and lvs_result.get("netgen_subproc_code")==0
               and "Netlists do not match" not in lvs_text
               and ("Cell pin lists are equivalent" in lvs_text or "Netlists match uniquely" in lvs_text))
    rec={"name":name,"expected":expected,"bbox_um":[float(comp.xsize),float(comp.ysize)],
         "drc_result":drc_result,"lvs_result":lvs_result,"drc_clean":drc_clean,"lvs_match":lvs_match}
    for p in (gds,cdl,drc,lvs):
        rec.setdefault("files",{})[p.name]={"sha256":sha256(p),"bytes":p.stat().st_size}
    if not drc_clean: raise RuntimeError(f"{name}: DRC not clean")
    if not lvs_match: raise RuntimeError(f"{name}: LVS not proven match")
    return rec

tools={k:version(k+" --version") for k in ("magic","netgen")}
devices=[
 run_one("ptat_nmos_small", nmos(sky130,width=1.0,length=0.5,fingers=1,multipliers=1,with_tie=True,with_dummy=True,with_dnwell=False,with_substrate_tap=False),
         {"device":"sky130_fd_pr__nfet_01v8","w_um":1.0,"l_um":0.5}),
 run_one("ptat_nmos_large", nmos(sky130,width=8.0,length=0.5,fingers=1,multipliers=1,with_tie=True,with_dummy=True,with_dnwell=False,with_substrate_tap=False),
         {"device":"sky130_fd_pr__nfet_01v8","w_um":8.0,"l_um":0.5}),
 run_one("ptat_pmos_branch", pmos(sky130,width=4.0,length=1.0,fingers=1,multipliers=1,with_tie=True,with_dummy=True,dnwell=False,with_substrate_tap=False),
         {"device":"sky130_fd_pr__pfet_01v8","w_um":4.0,"l_um":1.0})
]
manifest={
 "schema_version":1,
 "status":"PASS" if all(d["drc_clean"] and d["lvs_match"] for d in devices) else "FAIL",
 "evidence_class":"Real SKY130 primitive physical-tool qualification; not PTAT top-level physical signoff",
 "generated_utc":datetime.now(timezone.utc).isoformat(),
 "pdk_root":os.environ.get("PDK_ROOT"),
 "pdk_revision":"12df12e2e74145e31c5a13de02f9a1e176b56e67",
 "openfasoc_commit":os.environ.get("OPENFASOC_COMMIT"),
 "container_image":os.environ.get("OPENFASOC_IMAGE"),
 "container_image_id":os.environ.get("OPENFASOC_IMAGE_ID"),
 "tools":tools,
 "devices":devices,
}
mp=OUT/"physical_toolchain_probe_manifest.json"
mp.write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
print(json.dumps(manifest,indent=2))

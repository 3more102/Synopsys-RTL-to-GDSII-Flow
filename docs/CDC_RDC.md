# CDC / RDC Policy

Synthesis `check_design` and static timing do not replace clock-domain-crossing or reset-domain-crossing verification. The base repository therefore labels CDC/RDC as a separate optional signoff activity. Integrate SpyGlass CDC/RDC, Questa CDC, VC CDC or another qualified methodology using the project's actual clocks, resets, synchronizer policy and waivers. Waivers must be reviewable and justified; never silence CDC/RDC crossings merely to make reports green.

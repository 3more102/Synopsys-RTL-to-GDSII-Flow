# Optional DFT hook
The base flow does not insert scan because scan style, test clocks/resets, scan cells, chain count and ATPG methodology are project/library specific. Add a Design Compiler/TestMAX DFT script only after those inputs are defined. Physical implementation should then preserve scan-chain information and test-mode SDC.

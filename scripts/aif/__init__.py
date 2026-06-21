"""Active-inference reformulation of the waiter behaviors.

See docs/aif_design.md. `generative_model` builds the POMDP (A/B/C/D + law-as-code
norm seams); `aif_coordinator` is the EFE-minimising decision core and a headless
demo. This is a drop-in alternative to ReactiveCoordinator's argmax arbitration.
"""

# Quantization group-size sensitivity, version 1

Frozen before the first follow-up run in [issue #1](https://github.com/Whyme-Labs/hadamard-exposition/issues/1), created 17 October 2026 at 12:13 UTC.

This protocol is recorded before running the follow-up experiment.

- Cases: the existing isotropic Gaussian and persistent activation-outlier constructions.
- Data: 512 activation rows, 128 input features, 64 output features, seeds 0 through 19.
- Outlier construction: multiply activation feature zero by 32.
- Bases: original coordinates and the existing full-width randomized Hadamard basis.
- Rotation: the same independent signs from seed + 100000, shared across cases and all group sizes. No rotation selection or tuning.
- Quantization group sizes: 128, 64, 32 and 16 contiguous input features.
- Activations: groups within each row. Weights: groups down each output column.
- Both arms use the same group size, scale count, maxabs rule, four-bit codes -7 through +7, and ties-to-even rounding. Their numerical scales are recomputed in their own bases.
- Primary endpoint: paired difference in relative squared linear-output error for the persistent-outlier case at group size 32.
- All other case and group combinations are prespecified sensitivity results and must be reported.
- Aggregate seed-level errors with arithmetic means. Retain paired differences, rotation-win counts, and reduction in mean error. Keep activation, weight, activation-only output and weight-only output diagnostics.
- Use 10,000 paired bootstrap resamples of whole seed records, with seed 20261017, for descriptive 95% intervals. Reuse resampling indices across settings.
- The 20 seeds have already been inspected in the reference study. This is a prespecified follow-up sensitivity study, not independent confirmation.
- Preserve the original grid-aligned counterexample in the reference experiment. It is not included in the group sweep because its forced maximum at feature zero does not guarantee exact representation in every smaller group.
- Retain all 160 paired case/seed/group records, runtime versions, protocol and source hashes, scale counts and measured wall time.
- Run locally on CPU with one BLAS thread and a 180-second process deadline. No model, external dataset, GPU or paid inference is involved.


## Numerical acceptance

For group size 128, compare each Gaussian and persistent-outlier seed against the retained reference records. Use relative tolerance 2e-12 and absolute tolerance 2e-14 for numerical metrics. Require matching seed and case identities, 160 unique paired cells, finite outputs, and matched scale counts. Before rounding, the normalized change-of-basis relative Frobenius difference must be below 2e-13.

For descriptive bootstrap intervals, compute the 2.5th and 97.5th percentiles of the 10,000 resampled means using NumPy's linear quantile interpolation. A negative paired error difference favors rotation. Percentage-point differences are 100 times the difference between squared-error ratios. Reduction in mean error is one minus the rotated mean divided by the original mean.

Changing group size changes the number of scales. It does not measure packed memory, scale precision, storage compression, latency or throughput. The full-width transform is unchanged throughout the sweep. Smaller groups can change the rounding grid, so monotonic realized-error improvement is not assumed.

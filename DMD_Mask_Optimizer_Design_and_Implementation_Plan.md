# DMD Mask Optimizer
## Full design and implementation plan

**Project** DMD Optimizer Planner - Execute  
**Revision** 2.1  
**Prepared** November 15, 2026  
**Status** Proposed implementation design with a fixed MVP compatibility fixture. Source documentation and selected original editor functions have been reviewed. No optimizer, native capture, or exported project has been executed in preparing this plan; those remain validation work, not unresolved product decisions.

## 1. Confirmed product requirements

Create a fully automatic Windows desktop application that prepares comparison masks and reference frames before Serum colorizing begins. The user loads a ROM of their choice and can add raw dump files. The application identifies the ROM revision, checks its assets, detects native DMD geometry and shade encoding, explores its output, optimizes recognition, and exports the results.

| Requirement | Confirmed decision |
| --- | --- |
| Optimization target | Minimize distinct active comparison masks used to recognize incoming DMD frames |
| Authoring workflow | Process ROM output before colorizing begins |
| ROM selection | User loads a ROM of their choice through the application |
| Coverage objective | Every possible output of that selected revision across its supported languages and machine settings |
| Automation | Entire processing workflow is automatic |
| Permitted variable content | Scores, credits, timers, other numeric values, player names, initials, and variable text |
| Preserved distinctions | Moving graphics, animation changes, and brightness differences outside permitted variable fields |
| Available inputs | Local ROM files and dumps, with automated emulation and ROM analysis allowed |
| Outputs | Editable Serum project plus separate masks, reference frames, mappings, and a coverage report |
| Editor | Original ColorizingDMD from the supplied SerumColor repository, with version selection and pinning delegated to implementation |
| Interface | Windows desktop application |
| Default run budget | 30 minutes, configurable per run |
| Optimization acceptance | Best verified solution found within the budget |
| Incomplete coverage | Save provisional results and clearly report established coverage and unresolved gaps |
| Uncertain grouping | Keep reference frames separate, export verified results, and flag the unresolved grouping |

The product supports ROM selection at runtime. Development fixtures may exercise particular ROMs without making one title a product requirement. Each emulator driver and output format needs tested support. A selected ROM with missing assets or unsupported DMD delivery semantics receives an explicit diagnostic.

The final color artwork is created later in ColorizingDMD. Verification here establishes frame recognition, retained distinctions, source-data preservation, and project usability. Artist intent and final colors are established during subsequent colorizing.

## 2. Optimization contract and safe automatic grouping

The primary metric is the number of distinct active custom comparison-mask bitmaps. A shared bitmap counts once. A rule with no comparison mask has zero custom-mask cost. Count reference frames, uncertain groups, and mask/mode combinations separately.

A finite dump can often be represented using one unmasked reference for every unique image. Numeric values then produce many references and unseen values remain uncovered. The optimizer must therefore establish which numeric/text variations belong to the same recognition family before reducing mask count.

A frame family contains the same fixed visual layout and animation state with permitted numeric/text variation. Static text such as a scene title is a distinguishing feature. Variable text requires supporting evidence from ROM behavior, rendering provenance, or observed recurrence. Similar glyph shapes alone are insufficient.

The automatic grouping contract is as follows.

1. Infer permitted variable regions and retain the evidence and supported value domain.
2. Group only frames whose retained visual content agrees and whose changes are confined to established variable regions.
3. Freeze each evidenced family during a solve. Its rule must recognize the whole established family domain.
4. Keep uncertain cases as separate reference frames and record why generalization is unresolved.
5. Allow multiple families to share a bitmap when recognition remains valid.
6. Treat new counterexamples as a new family/corpus revision and revalidate affected results.
7. Preserve every original input and occurrence so downstream colorizing can revisit a grouping.

The user has accepted separate references for uncertain cases. The optimizer must not split an established dynamic family merely to improve its mask metric. Report mask savings together with the number of unresolved singleton references and the scope of dynamic generalization.

Use strict discrimination initially. Every active rule must reject covered incompatible visual families, regardless of matching order. This is an engineering choice to make automatic verification reliable. Its feasible space and resulting mask bounds are stated explicitly.

Once a candidate is valid, prioritize fewer masks, then fewer redundant references, then measured runtime cost. Correctness, supported generalization, and format limits are hard constraints. Shape mode is disabled for the initial product because the user requires brightness distinctions outside ignored variable fields.

A colorization-specific rule for identical source frames with different intended colors or triggers cannot be inferred from raw pixels alone. Preserve occurrence context and flag such conflicts when they are discoverable. Describe recognition verification in terms of the documented visual grouping policy.

## 3. Verified upstream behavior and compatibility contract

The following findings establish the starting point. Links point to the inspected upstream material. Branch pages can change, so implementation must resolve these references to commit hashes and retain the checked source versions.

| Finding | Design consequence | Evidence |
| --- | --- | --- |
| PinMAME distinguishes luminance output for rendering from raw frames used for identification. | Capture and normalize the exact identification input sent to Serum. | [PinMAME DMD documentation](https://github.com/vpinball/pinmame/blob/master/docs/dmd.md) |
| The inspected editor header defines 64 comparison-mask slots and uses 255 as the unmasked frame sentinel. | The initial original-editor profile uses those limits. Each additional profile verifies its own limits. | [ColorizingDMD cRom.h](https://github.com/SerumColor/ColorizingDMD/blob/master/cRom.h) |
| The inspected comparison CRC helper processes pixels whose mask value is zero. Shape mode maps values greater than one to one. | Keep pixels in scan order, omit hidden pixels from CRC input, and reproduce the exact transform. | [ColorizingDMD crc32.cpp](https://github.com/SerumColor/ColorizingDMD/blob/master/crc32.cpp) |
| The original bundled decoder starts searching from the last match and checks references sharing mask and shape settings. | Verify sequences and state-dependent search behavior. | [ColorizingDMD serum-decode.cpp](https://github.com/SerumColor/ColorizingDMD/blob/master/serum-decode.cpp) |
| Current PPUC libserum documentation describes a 3.0 line using Serum v2 and cROMc, with authoring APIs. | Select and test an editor/runtime pair before deciding the export path. | [PPUC libserum](https://github.com/PPUC/libserum) |
| libdmdutil provides dump playback and machine-readable comparison tools. | Evaluate those tools as an integration-test component. | [libdmdutil](https://github.com/vpinball/libdmdutil) |

The original formats.txt describes an earlier serialization layout. Use the selected editor's actual serializer and loader to establish the version-specific schema. The full current PPUC matching implementation was unavailable during this review. Its internal precedence, hashing path, and state behavior remain implementation discovery items. [Original format description](https://github.com/SerumColor/ColorizingDMD/blob/master/formats.txt)

Create a compatibility profile containing the following fields.

| Area | Required profile information |
| --- | --- |
| Provenance | PinMAME, editor, runtime, and optional replay-tool repository, tag, commit, build flags, and binary digest |
| Input | Capture producer, dump grammar, native width/height, shade encoding, coordinate order, raw-to-runtime transformation |
| Matching | Mask polarity, comparison resolution, shape transform, CRC parameters and traversal, lookup key, precedence, repeated-frame behavior |
| Serialization | Project and runtime format versions, identifiers, mask/frame limits, field widths, endianness, export API |
| Playback | Time units, clock behavior, reset behavior, color rotations, sprite/scene events, output planes, unknown-frame behavior |
| Certification | Fixture results, supported feature combinations, and unresolved compatibility findings |

Do not infer native comparison resolution from the colored output size. The inspected original CRC source includes special handling for some 256 × 64 data. Each resolution requires a fixture proving the actual comparison pixels. [CRC source](https://github.com/SerumColor/ColorizingDMD/blob/master/crc32.cpp)

## 4. Coverage, verification, and completion status

Keep run completion, recognition verification, output coverage, and mask optimality as separate fields.

| Field | Example states | Meaning |
| --- | --- | --- |
| Run status | Completed budget, cancelled, failed, finished early | Why processing stopped |
| Recognition status | Verified on named corpus/domain, verification failed, unverified | Which assignments passed exact matching checks |
| Coverage status | Captured corpus, modeled families, complete ROM domain, incomplete | Which possible inputs have been established |
| Optimization status | Feasible, candidate optimum, policy-scoped all-mask optimum, unknown | Strength of the mask-count result |
| Export status | Verified editable project, partial verified subset, diagnostic data only | What the output can safely represent |

A normal 30-minute run may end with a verified provisional project. Complete ROM coverage remains the objective. Claim it only after a complete reachability result or a sound argument connecting every reachable output to verified families.

The coverage manifest records ROM and parent dependencies, emulator build, language/settings combinations, initial-state and NVRAM domains, exploration frontier, and any time or input bounds. Every supported language and machine setting is included in the target domain. Combinations still unexplored or unmodeled are listed as unresolved.

It may be impossible to enumerate unknown outputs or compute a defensible percentage of all reachable ROM frames. Report known counts, tested configurations, unexplored states, and unproved obligations. Use an unknown total where the denominator is unknown.

Absolute minimum proof is optional. Record the best verified mask count and any valid bound. A candidate-pool bound applies to that candidate pool. A strict-discrimination bound applies to that policy.

## 5. System architecture

Use a local Windows application with a persisted project and isolated workers for emulation, analysis, optimization, and native Serum playback. Windows x64 is the initial build target selected for implementation.

| Component | Responsibility | Main output |
| --- | --- | --- |
| ROM loader | Resolve selected ROM revision and dependencies, detect driver and DMD format | ROM identity and support diagnostics |
| Exploration worker | Exercise languages/settings, collect identification frames, inspect renderers | New captures and coverage frontier |
| Capture adapters | Parse supplied dumps with exact producer semantics | Validated frame occurrences |
| Corpus store | Deduplicate pixels while retaining every occurrence and source | Immutable corpus revision |
| Family analyzer | Establish numeric/text variability automatically and isolate uncertain cases | Evidence-backed family domains |
| Candidate generator | Construct reusable masks and check discrimination | Candidates and counterexamples |
| Solver | Reduce distinct masks within the remaining budget | Verified incumbent and scoped bounds |
| Runtime verifier | Reproduce exact matching and replay exported fixtures | Match and behavior diagnostics |
| Editor adapter | Create an editable original-ColorizingDMD project | Verified project and separate exports |
| Desktop interface | Load inputs, configure runtime budget, run, inspect status, open output | Completed or provisional result |
| Report writer | Explain coverage, grouping evidence, differences, and optimization | Human- and machine-readable reports |

The proposed stack is Python, NumPy, SQLite, packed bitsets, OR-Tools CP-SAT, PySide6, and C++ wrappers for the pinned PinMAME/Serum builds. Freeze exact dependencies after compatibility tests. An internal command runner supports automated testing and worker operation. The user-facing deliverable is the desktop application.

CP-SAT provides distinct feasible, optimal, infeasible, invalid, and unknown statuses. Preserve those meanings in reports. [OR-Tools documentation](https://developers.google.com/optimization/cp/cp_solver)

Use one runtime instance per process until state ownership and thread safety have been verified. Use versioned local IPC with bounded frame messages, timeouts, process exit diagnostics, and cancellation.

| Module path | Contents |
| --- | --- |
| src/dmd_optimizer/rom/ | ROM identity, dependency checks, driver profiles |
| src/dmd_optimizer/explore/ | Capture scheduling, state frontier, language/settings enumeration |
| src/dmd_optimizer/capture/ | Dump parsing and input normalization |
| src/dmd_optimizer/corpus/ | Pixel chunks, occurrence indexing, revisions |
| src/dmd_optimizer/families/ | Automatic grouping and evidence |
| src/dmd_optimizer/masks/ | Candidate generation and discrimination |
| src/dmd_optimizer/solve/ | Candidate and direct synthesis models |
| src/dmd_optimizer/verify/ | Runtime replay and result comparison |
| src/dmd_optimizer/adapters/ | Original editor integration |
| src/dmd_optimizer/ui/ | Windows desktop workflow |
| native/ | PinMAME and Serum worker wrappers |
| schemas/ | Versioned project, IPC, interchange, and result formats |
| tests/fixtures/ | Synthetic and permitted real-data fixtures |

## 6. Input and capture design

Implement the precise text-dump variant accepted by the chosen ColorizingDMD version first. Confirm its grammar against real samples, including timestamps, frame delimiters, hexadecimal symbols, and line endings. Add raw and ZIP inputs through separate adapters after fixtures exist.

The parser must validate dimensions, row lengths, shade ranges, numeric overflow, truncated records, timestamps, and supported encoding. Report the source file and line or byte offset for malformed input. Reject partial frames explicitly. An optional diagnostic import can retain valid records while marking the corpus incomplete.

Preserve native shade values. Keep any transformation needed by the selected runtime explicit and reproducible. Spatial rescaling and temporal filtering require their own verified profile.

Store each occurrence with its original order and timestamp. Deduplicate raw pixel payloads without discarding occurrence records. Preserve repeated frames because event and animation behavior can depend on repeat calls and elapsed time. Mark missing final duration and inferred timing explicitly.

Recognize timestamp resets and wraps through the producer profile. Start a new session where needed. A corrupt or ambiguous timestamp must generate a diagnostic instead of silently creating negative or enormous playback duration.

Identify frames by a digest over geometry, encoding, normalization version, and pixel bytes, then confirm bytes on digest matches. Runtime CRC remains a separate attribute.

For new capture collection, cover boot, attract sequences, single and multiplayer games, score layouts, credits, service modes, bonuses, extra balls, match sequences, named modes, multiball, failures, initials, language variants, transitions, and interrupted animations. Capture short-lived frames with the same delivery semantics used during play.

PinMAME's remote-debug recorder is documented as a short ring buffer of luminance frames. Evaluate it for exploration, while verifying a lossless identification-frame capture hook for optimization. Its checkpoint features have platform limits and cannot establish complete emulator state by assumption. [Remote debugger documentation](https://github.com/vpinball/pinmame/blob/master/src/remote_debug/README.md)

## 7. Data model and reproducibility

Use SQLite transactions for metadata and append-only frame chunks for pixel payloads. Write chunks and checksums before committing metadata references. Clean up orphan chunks after interrupted writes.

| Entity | Essential fields |
| --- | --- |
| Project | schema version, project ID, ROM identity, compatibility-profile digest, current corpus revision |
| Capture | source digest, producer/version, settings, session, timestamp semantics, completeness, storage location |
| Frame | stable ID, geometry, shade encoding, raw digest, normalized digest, chunk offset and length |
| Occurrence | capture ID, sequence index, frame ID, time, duration status, original source offset |
| Recognition expectation | stable family ID, retained-pixel specification, established variable domain, renderer evidence, context |
| Family | ID, positive examples, recognition expectation, allowed variants, evidence status, permitted transforms, recognition-rule budget |
| Constraint | family, established must-ignore/must-compare pixels, assignment restrictions, evidence and source |
| Mask | ID, dimensions, canonical ignore bitmap, digest, source, visibility statistics |
| Candidate rule | family, reference, mask or None, shape setting, runtime CRC, tested coverage, conflicts |
| Solve run | input digests, model version, seed, limits, solver version, status, incumbent, lower bound, proof scope |
| Verification | exported artifact digest, runtime build, sessions, mismatches, output/event checks, performance |
| Export | source project digest, solution digest, stable-to-editor ID map, file manifest, compatibility profile |

Internally use an ignore bit of one and a compared bit of zero. The editor adapter converts this canonical representation to its exact byte encoding. Geometry and profile are part of mask identity. Masks with identical bytes in different geometries are distinct.

Model recognition equivalence using the established numeric/text variation policy, retained pixels, and relevant source context. Preserve source reference identifiers through a mapping even if export compacts indices. Later authored colors, sprites, rotations, and triggers belong to the downstream colorization project.

All long-running stages use immutable input revisions. New captures or author edits create a new revision and invalidate dependent candidates and proofs. Cache keys include the corpus, family specification, runtime profile, algorithm version, and relevant settings.

A cancelled solve retains only previously verified results. A resumed job reuses those results as hints and rechecks input digests. Solver execution state is resumed only if the chosen solver version supports it.

## 8. Automatic family inference

Infer families from raw ROM output and supported ROM-rendering evidence. An existing colored project is unnecessary for normal operation.

Start with exact duplicate frames and recurring layouts across captures. Segment animation states without averaging pixels. Track regions whose changes are consistent with numeric fields or variable text. Where available, connect those regions to ROM rendering operations, font/glyph data, value sources, and layout logic.

For a proposed dynamic field, model width, alignment, sign, punctuation, clipping, glyph set, and value range. A set of observed digits establishes only an observed domain until additional evidence supports generalization. Correlated changes across fields need a joint model.

Preserve static labels, moving graphic states, animation steps, and visible intensity differences. A sliding score or text field requires an explicit model of its position and the surrounding animation state. Movement alone is insufficient evidence that a region can be ignored.

Classify each grouping as established for a stated domain, observed-only, or uncertain. Established groups can be generalized over their verified domain. Observed-only groups carry a limited coverage claim. Uncertain groups retain separate references and a report entry, with no required user review.

Keep every raw frame and occurrence accessible through the mapping export. An uncertain reference may use full-frame matching if it passes exact runtime checks. A collision or format limit can still make it unrepresentable, in which case report that input explicitly and export the verified subset where feasible.

For testing, developers use independently labeled synthetic fixtures and known ROM-renderer cases to measure incorrect merges and missed merges. Those test labels do not create a manual step in the shipped application.

The editable project contains the original reference data, assigned comparison masks, source sequence mapping, and an initial grayscale authoring state as needed by the editor. Dynamic coloring and final artwork are authored later. Export must preserve access to ignored numeric/text content so that authoring remains possible.

## 9. Candidate generation and validity

Let F_g be the established input domain for family g, r_g its representative, and T_s the profile's transform. The current product allows normal comparison only, so s=0. Let m(p)=1 mean pixel p is ignored. Shape-mode machinery described in the general model is retained only as a disabled extension.

A necessary family-invariance condition is that every compared transformed pixel has the representative's value for every member of F_g. Derive the variability set D_g,s of all positions that can differ. Every valid mask for that family and mode must ignore D_g,s.

For each incompatible input h, derive E_g,h,s, the positions at which T_s(r_g) differs from T_s(h). At least one compared position must remain in this set for logical discrimination. If every such position must also be ignored, the family and negative input cannot be separated under that mode and definition.

Build candidates in this order.

1. Existing masks, deduplicated by canonical bytes.
2. Unmasked matching in normal mode.
3. Minimum ignored regions required by each family's variability.
4. Unions of ignored regions across promising family combinations.
5. Variants with selected stable distinguishing pixels retained.
6. Direct solver-generated masks for uncovered families or better sharing.
7. Revised candidates produced from verified counterexamples.

The union of ignored regions allows reuse across families but can erase their distinguishing content. Recompute validity after every union. Pairwise-valid sharing also requires a check on larger combinations. Keep higher-order conflicts rather than assuming a pairwise compatibility graph is complete.

For each candidate, evaluate positive-family invariance, logical discrimination, exact runtime CRC, actual lookup behavior, and export limits. Compare it against every incompatible input in the covered domain, including frames belonging to other masks. Input from an unrelated scene is still offered to the selected rule at runtime.

Equal compared bytes are an intentional or accidental semantic match. Different compared bytes with equal CRC are a hash collision. Record both. A full-byte comparison used in the optimizer explains the collision, while acceptance must follow the target runtime's actual CRC behavior.

A fully ignored mask is legal for optimization only if every possible input it can capture has compatible behavior under the selected policy. Mixed projects will generally fail this check.

Candidate pruning must preserve selectable alternatives. Duplicate rules can be removed when mask bytes, mode, behavior, and effect on the model are identical. Broader dominance pruning requires a proof that coverage, conflicts, locks, costs, and runtime behavior are no worse. Retain alternatives when that proof is unavailable.

## 10. Candidate-pool optimization model

Use a set-cover-style assignment model with shared mask costs.

Let G be the frozen set of families, M the candidate mask bitmaps, and O_g the verified options for family g. An option includes its reference and mask or None. Its shape-mode field is fixed to false for the current product. Define binary y_m indicating that bitmap m is used, and binary z_g,o indicating the option chosen for family g.

Minimize

    K = sum(y_m for m in M)

subject to

    sum(z_g,o for o in O_g) = 1                       for each family g
    z_g,o <= y_mask(o)                               for each custom-mask option
    y_m <= sum(z_g,o for options using m)             for each bitmap m
    K <= profile.max_comparison_masks

Remove options violating established family invariance, format constraints, or the coverage domain of the solve. Unmasked options have no y variable. Reuse of the same bitmap across families incurs one unit of K.

For the first release, use strict discrimination. A selected rule must reject every covered incompatible input, independently of runtime precedence. This permits complete candidate validation before solving. The resulting minimum is explicitly scoped to strict discrimination.

A future extension can consider overlaps resolved by runtime state through a separate policy. Its model uses selected rule combinations, actual search order, and reachable verifier states. Pairwise exclusion constraints can express some conflicts. Other failures require higher-order constraints or exact replay-based exclusions. These policies have different feasible spaces and their bounds remain distinct.

Start with a deterministic greedy cover, then remove unused masks and attempt reassignment. Feed that feasible solution to CP-SAT. Run the model within the overall controller's remaining time and memory budget, preserve the best verified result, and report the solver bound. Use staged objectives to avoid an arbitrary tradeoff between mask count and secondary costs.

An optimal solution to this model proves the minimum within O_g and the declared policy. A restricted candidate pool can miss a useful bitmap, so its lower bound is not automatically a lower bound for all masks.

## 11. Optional search beyond the candidate pool

Add a direct synthesis model to search all masks allowed by the canonical geometry and family specification.

For a trial limit K, define up to K mask slots. Variable v_k,p says that pixel p is compared by slot k. Assignment variables choose a slot for each family, with an additional unmasked option. Mode s is fixed to normal comparison.

Reified constraints require the following whenever family g uses slot k in mode s.

- v_k,p equals zero at every position in D_g,s.
- At least one v_k,p equals one in each difference set E_g,h,s for incompatible h.
- Established pixel-domain, geometry, assignment, and mask-limit constraints hold.
- Each family has exactly one selected rule under its declared budget.

Use symmetry breaking for interchangeable mask slots. Treat identical active bitmap slots as one mask when validating an incumbent. Search from a lower bound toward the best known feasible K, or minimize active slots directly.

The pixel model is a relaxation of the full CRC-aware strict-discrimination problem. It enforces compared-content invariance and separation but initially omits accidental CRC equality. Its valid lower bound can support a mask-minimum proof for that declared problem.

For every proposed solution, materialize masks and use the runtime oracle. When a CRC collision or other runtime failure appears, exclude the offending exact configuration using a sound constraint, then solve again. Exclude only configurations demonstrated to fail. Arbitrary broad exclusions can invalidate a minimum proof.

A small bit-vector/SAT verifier may later encode the CRC update, conditional byte omission, and exact matching logic to check collision conditions over symbolic domains. Benchmark that approach before relying on its scale.

Use lazy negative-example constraints and counterexample generation to avoid constructing all family-by-frame comparisons up front. A finite-domain proof requires a complete checker to show that no additional counterexample exists. Random fuzzing supplies evidence and counterexamples, with its sampling scope recorded.

An all-mask minimum under strict discrimination still has that policy restriction. Proving a smaller minimum that uses runtime ordering requires a complete model of the allowed order-dependent strategies, reference budgets, and reachable runtime states. That extension is part of the advanced proof work.

## 12. Proof results and example

Every verified feasible result includes an upper bound U. Include a lower bound L and gap U-L only when that bound has been established for the same model. Results with no verified feasible assignment leave U unset. All results include the optimization policy, candidate/domain definition, and source digests.

| Result | Required interpretation |
| --- | --- |
| Feasible, candidate search | A tested solution exists. Search may improve it. |
| Optimal, candidate pool | U equals L for the exact candidate model. |
| Optimal, all masks under declared policy | A verified result meets a lower bound applying to every allowed mask under that policy. |
| Infeasible, candidate pool | The selected candidates cannot meet the constraints. Expand generation or diagnose the family model. |
| Infeasible, complete model | No solution exists under the declared domain, reference budget, policy, and format limits. |
| Unknown or cancelled | No proof of infeasibility or optimality follows. Preserve any independently verified incumbent. |

For example, suppose three dynamic families initially use masks A, B, and C. If A and B can share a union mask while C must use another, the tool may return U=2. A candidate-pool proof of two establishes only that pool's minimum. A direct-model lower bound of two, paired with the same verified solution, establishes the minimum for all masks in that model. This is an illustrative example, not a measured result for a ROM.

Proof records contain solver version, parameters, model digest, bounds, input definitions, and checker output. Describe a result as solver-proven unless a separately checkable proof artifact has actually been generated and validated.

## 13. Recognition and runtime verification

Build a small native worker around the selected Serum implementation. Expose load, reset, process frame, advance time, query result, and dispose through a versioned test protocol. Optional test instrumentation can expose reference selection when the public API cannot. Verify observable parity with the corresponding production build.

The baseline for this pre-colorizing tool is the established visual family policy and original source data. Use synthetic authoring colors and identifiers in test packages to reveal which reference was selected. Final artist colors are outside this verification contract.

For each occurrence, record its input identity, timing, selected stable reference/family, runtime result, and any observable reset/repeat/continuation effects. Verify these stages.

1. CRC parity for masks, full-frame references, and profile-specific transforms.
2. Correct family recognition and separation across all known input frames.
3. Full ordered replay, including repeated input and original timing.
4. Relevant preceding states and reset conditions.
5. Independent capture sessions and new numeric/text values.
6. Generated domain variants and confusable negative examples.
7. Preservation of source/reference pixels and editable metadata.
8. Editor reopen, runtime export, runtime load, and replay.
9. Revalidation after final mask IDs and reference order are assigned.

Record correct matches, incorrect-family matches, unknown inputs, and unresolved references separately. An unknown-frame fallback is an unresolved recognition result when a specific reference is required.

Reserved sessions stay outside inference and optimization until their validation role is finished. When a failure becomes training input, record that change and reserve fresh sessions where possible.

A result can be verified on captured frames while its inference or full-ROM coverage remains provisional. An automatic grouping confidence score alone cannot establish semantic correctness or exhaustive coverage.

Use existing libdmdutil playback and JSON comparison capabilities where a pinned build meets the fixture requirements. [Playback tools](https://github.com/vpinball/libdmdutil)

## 14. Original ColorizingDMD project creation and separate exports

Select and pin a compatible build from the original SerumColor ColorizingDMD line. Resolve source and binary checksums, then prove a minimal project can be created, opened, saved, exported, and replayed. The exact version and runtime pairing are implementation decisions delegated by the user. They remain technically unverified at this planning revision.

Use the editor's actual data model and serializer through a small integration bridge where feasible. A standalone project writer is acceptable after round-trip fixtures establish the required schema and metadata. The desktop workflow must generate the project automatically.

Create a new authoring project from the ROM identity, reference frames, comparison masks, frame assignments, source sequence information, and required default authoring metadata. Use the selected original editor's real companion-file conventions.

The separate export bundle includes the following proposed files.

| Output | Contents |
| --- | --- |
| masks.json | Canonical bitmaps, geometry, polarity, stable IDs, editor-slot mapping, digests |
| masks/ | Lossless visual mask previews with documented ignored/compared values |
| reference_frames/ | Exact native shade values plus lossless previews and geometry metadata |
| frame_mapping.csv | Capture/sequence/frame identity to reference, family, mask, and status |
| optimization.json | Search limits, counts, verified incumbent, bounds and proof scope |
| coverage.json | Tested configurations, discovered frames, domain proofs and unresolved gaps |
| report.html | Readable results with concrete uncertain groups and failed cases |

The JSON and CSV formats are optimizer-defined exports. They are delivered alongside the native editable project. Raw pixel payloads remain authoritative for matching.

For every export, validate the source revision, compile canonical masks to editor slots, assign stable mappings, recompute checksums, write to a temporary project directory, reopen, verify, and atomically publish the bundle. The report identifies the exact input revision and tested export digest.

If uncertain groups have valid separate references, include them and flag their unresolved generalization. If some inputs cannot be represented because of a collision, missing data, or editor limit, export a verified subset only when it forms a valid project and identify the omitted inputs. If no valid editable project exists, save diagnostic/source exports with the specific failure.

Allow resuming from an earlier run. A newly created project includes a manifest identifying its previous result where applicable. Repeated export of the same run produces equivalent content and does not silently overwrite an author's edited project.

## 15. Windows desktop workflow and run controller

The normal workflow is Load ROM, optionally Add Dumps, choose output folder and run limit, then Start. All family inference, emulation, optimization, and verification run automatically. Results may be inspected without becoming a required approval stage.

| Work area | Required controls and feedback |
| --- | --- |
| Inputs | ROM selector, detected revision/dependencies, optional dump selector, display geometry |
| Run | Configurable limit defaulting to 30 minutes, Start, Cancel, Resume saved work |
| Progress | Current phase, elapsed/remaining budget, discovered frames, verified mask count, tested configuration counts |
| Results | Verified scope, provisional status, unresolved groupings, mask/reference totals, failure witnesses |
| Export | Open editable project, open separate exports, open coverage report |

Keep numeric/text values visible in source previews. Display reference frames and mask overlays at integer scaling. Show a grayscale authoring preview until the user colorizes the project.

Treat the configured duration as the processing budget for one run, covering initialization, exploration, inference, solving, verification, and export preparation. Reserve time adaptively for validating and saving the best result. Save verified checkpoints throughout the run so that a late solver result does not displace a valid incumbent before verification.

At the deadline, stop scheduling additional work, cancel bounded worker operations, and persist the last verified state. Final filesystem flushing may require a short reported cleanup interval. The application never continues exploration indefinitely after this deadline by default.

Validate new captures and candidates incrementally. If the corpus has grown beyond a saved solution's verified scope, export that solution with its exact earlier corpus revision and list the newly discovered inputs as pending. Never label it as verified against the expanded corpus.

If no candidate solution has been verified, attempt an already-validated exact-reference baseline for representable captured inputs. If no valid baseline is available, retain source and diagnostic data and report that an editable project could not be generated.

Resume is an explicit subsequent run with a new configurable budget. Reuse the compatible corpus, frontier, candidates, and verified solution. Recheck digests and invalidate stale dependencies. The application remains responsive, and worker failures become concrete diagnostics.

## 16. Capacity, runtime budget, and recovery

Use an initial engineering benchmark of one million occurrences, up to one hundred thousand unique 128 × 32 inputs, and one thousand established families on an 8-core Windows machine with 16 GB RAM. This sizing assumption must be measured and revised. Support other native geometries through tested profiles.

One hundred thousand frames at one byte per pixel require about 410 MB before metadata. A 128 × 32 bitmap occupies 512 bytes as a packed bitset. Stream captures and avoid dense candidate-by-frame-by-pixel tensors.

Compute variability once per family, keep sparse negative witnesses, cache exact CRCs by input/mask/mode/profile, and add solver constraints lazily. Parallelize independent validation through bounded workers with a configurable resource cap. Automatically leave capacity for the desktop interface.

The 30-minute limit is a user requirement. No fixed runtime allocation to capture versus solving is assumed. The scheduler reserves verification/save capacity and adapts the remaining budget using discovered novelty, unresolved groups, and time since the last verified improvement.

Checkpoint every verified improvement and at bounded intervals. Persist corpus metadata transactionally and write data chunks before their references. On restart, validate checksums and ignore incomplete chunks. Resume from compatible persisted work, with the previous result available independently of new processing.

Measure match latency, end-to-end runtime processing latency, peak memory, result size, reference count, and mask count. Establish playback performance acceptance against the selected native delivery rate and supported hardware. Time-budget compliance and valid provisional export are tested independently of how many masks are saved.

## 17. Test strategy and acceptance criteria

| Area | Required cases |
| --- | --- |
| ROM loading | User-selected revision, parent dependencies, missing ROM, unsupported driver, geometry detection |
| Configuration scope | Multiple languages/settings, valid NVRAM variations, incomplete configuration enumeration |
| Parser | Line endings, shade alphabets, truncated data, dimensions, timestamp wrap/reset |
| Identity | Repeated payload with different timing, distinct inputs sharing a CRC, different geometry |
| Matching | Mask polarity, hidden-byte omission, byte order, native comparison resolution |
| Numeric/text inference | New values, initials, variable widths, static scene labels, uncertain dynamic regions |
| Required distinctions | Moving objects, animation steps, brightness changes outside ignored variable fields |
| Automatic fallback | Separate uncertain references, known CRC conflict, report status, verified subset export |
| Sharing | Valid shared mask, invalid union, pairwise-compatible group with an invalid larger union |
| Solver | Tiny exhaustive cases, locked variables, unmasked baseline, infeasibility, timeout |
| Runtime state | Previous-match dependence, repeated frames, reset, transitions |
| Editor | Automatic new-project creation, reopen/save/export, correct IDs, preserved source data |
| Time and recovery | Deadline during exploration/solve/verification, cancellation, worker crash, resume, late new frames |
| Scale | Streaming input, bounded cache, large result bundle, UI responsiveness |

Use small synthetic instances with complete mask enumeration to verify the optimization models. These tests also demonstrate that a candidate-pool minimum and an unrestricted-mask minimum may differ.

Test the normal desktop entry point without requiring a user to review family groupings or edit intermediate files. An uncertain grouping must not stop unrelated analysis or prevent a valid provisional export.

A release passes when it can process user-selected supported ROMs, run automatic exploration/inference/optimization within the configurable budget, export a valid editable original-ColorizingDMD project and separate files, and report coverage honestly.

Every exported verified scope must have zero unexplained incorrect-family matches in its complete verification corpus/domain. Frames outside that scope must be identified as pending, unsupported, or uncovered. A full-ROM claim requires the complete proof obligations described in Section 18.

Global minimum proof is optional. Demonstrate mask sharing and reduced counts on suitable fixtures, while permitting zero savings when the input does not support a valid reduction. Establish compatibility and performance using multiple driver/geometry fixtures.

## 18. Automatic exploration and complete-ROM coverage

ROM exploration is part of the core product workflow. The application combines supplied dumps with automatically gathered identification frames for the selected ROM revision.

Enumerate languages and machine settings from verified driver/ROM metadata where possible. Exercise boot, attract, gameplay, modes, score layouts, text entry, service modes, diagnostics, and transitions. Persist configuration and exploration coverage. Unknown configuration domains remain explicit gaps.

Use scripted input sequences, switch events, mode targeting, state exploration, and rendering evidence to increase coverage. PinMAME simulation features vary by game, so driver adapters need exercised support. [PinMAME simulation documentation](https://github.com/vpinball/pinmame/blob/master/release/simulation.txt)

Document valid initial-state and NVRAM domains. Arbitrary corrupt persistent data and implementation-undefined behavior cannot be silently included in a complete claim. Any domain that has not been characterized remains an unproved obligation.

Two proof approaches can support complete ROM coverage.

- Explore every reachable complete state under the declared valid configuration/input model, check its outputs, and exhaust the frontier.
- Derive a sound display-behavior abstraction, prove every reachable output belongs to its family domains, and prove correct recognition over those domains.

A complete state includes all relevant memory, CPUs, devices, clocks, scheduler state, randomness, input latches, and persistent data. State merging requires equivalence with respect to future output. Partial debugger checkpoints require additional validation before use in a reachability proof.

Model numeric/text renderers with verified glyph sets, placement, clipping, and range constraints. Generated examples carry synthetic provenance. They support a full-ROM claim only when their connection to the ROM's reachable rendering behavior has been established.

A run with no new frames for a period has reached observed saturation. Complete coverage requires the stronger evidence above. At the deadline, save the frontier and obligations, export the verified result, and mark coverage provisional if closure is unproved.

When a counterexample appears, revise the corpus/family model, invalidate affected verification records, and re-optimize within the remaining time. Preserve the earlier verified result on its original scope.

## 19. Implementation milestones

Track engineering progress through demonstrated behavior and exit criteria.

| Milestone | Deliverable | Dependencies | Exit criteria |
| --- | --- | --- | --- |
| M0 — Compatibility | Pinned original ColorizingDMD/Serum/PinMAME profile and synthetic fixtures | Available source/builds | Minimal generated project reopens and matches the native runtime |
| M1 — Inputs and desktop shell | ROM chooser, dependency detection, dump parser, corpus store | M0 | Different supported ROM inputs load with reproducible identities and occurrences |
| M2 — Runtime oracle | Isolated worker, native CRC/matching tests, ordered replay | M0–M1 | Synthetic reference selection agrees with the editor/runtime |
| M3 — Exploration | Automated capture, languages/settings scheduler, persisted frontier | M1–M2 | Configurations are exercised and incomplete domains are reported |
| M4 — Automatic grouping | Numeric/text inference, evidence records, separate uncertain references | M2–M3 | Required visual distinctions survive and uncertain cases need no review |
| M5 — Optimization | Candidate generation, greedy incumbent, CP-SAT, scoped bounds | M4 | Small exhaustive tests agree and verified incumbents survive timeouts |
| M6 — Project and file exports | Native project creation, masks/references/mappings, coverage report | M0, M5 | Automatically generated project reopens and all separate outputs reconcile |
| M7 — Budget and recovery | 30-minute controller, checkpointing, cancellation, resume | M3–M6 | Deadline yields the last verified result with exact scope and unresolved gaps |
| M8 — Release validation | Packaged Windows application, support matrix, regression fixtures | M7 | Normal desktop workflow passes across representative drivers/geometries |
| M9 — Further search and proof | Direct synthesis, improved ROM abstractions, coverage and minimum proofs | M5–M8 | Any stronger claim is supported by a complete checker on its stated domain |

Direct synthesis may be brought forward when it improves practical results within the budget. Exhaustive-ROM proof is pursued through the shared coverage model and remains measurable separately from a successful provisional run.

Development can start with synthetic and available ROM fixtures. Fixture selection is an implementation responsibility. The user-facing application accepts a chosen supported ROM at runtime.

## 20. First implementation sequence

1. Resolve source versions for the original editor, an appropriate Serum runtime, and PinMAME. Record commit and binary digests.
2. Build an isolated runtime worker and generate minimal authoring fixtures.
3. Prove project creation, editor reopening, mask polarity, CRC parity, and reference selection.
4. Implement the Windows ROM chooser, dependency checks, and geometry/encoding detection.
5. Import dump occurrences losslessly and collect raw identification output through emulation.
6. Establish automatic families on numeric/text fixtures while preserving animation and brightness distinctions.
7. Demonstrate a shared comparison mask and validate it against incompatible frames.
8. Exercise uncertain-group fallback to separate references and a visible report entry.
9. Export the native editable project and separate mappings, then replay the exported recognition data.
10. Exercise the configured deadline during each phase and confirm recoverable provisional output.

Use results from this sequence to refine module boundaries, driver support, capture scheduling, and resource limits. Source and binary access or availability of representative test ROMs can affect which compatibility checks can be performed, and must be tracked as technical dependencies.

## 21. Remaining technical work and completion evidence

The user-facing requirements are resolved. The following engineering questions require investigation and executable tests.

| Technical item | Evidence needed | Status at this revision |
| --- | --- | --- |
| Exact editor/runtime pin | Resolved upstream source/binaries and passing create/reopen/export fixtures | Pending |
| Raw identification capture | Native input-byte parity for each supported driver/geometry | Pending |
| Automatic grouping reliability | Renderer evidence and independently checked cases, including uncertain fallbacks | Pending |
| Full-ROM configuration/state domain | Sound enumeration or abstraction, with all obligations recorded | Pending |
| CRC and matching-order correctness | Pinned implementation fixtures and ordered replay | Pending |
| Practical search performance | Real corpus measurements within the 30-minute controller | Pending |
| Project generation fidelity | Full original-editor round trip and mapping reconciliation | Pending |
| Driver and geometry support | Tested matrix across representative ROMs | Pending |

Version selection has been delegated to implementation. Available source review establishes several original-editor constraints, while release resolution and full runtime compatibility still need verification. No exact version or byte-level compatibility is claimed as validated here.

The implementation deliverables are the Windows desktop application, reusable engine, ROM exploration and runtime workers, original-editor project generator, separate mask/reference/mapping exports, regression fixtures, compatibility profiles, and reporting. Internal automation interfaces support development and testing.

Each result reports ROM identity, tested configurations, unique/total frame counts, established and unresolved families, mask/reference counts, verified scope, incorrect/unknown matches, runtime measurements, and the reason the run stopped. Bounds include their exact search scope. Complete-ROM coverage is claimed only with supporting evidence.

This revision incorporates the user's answers and replaces the earlier manual-review workflow, mandatory minimum proof, fixed pilot-ROM premise, and staffing-day estimates. Actual compatibility, automatic-analysis accuracy, measured performance, and exhaustive coverage remain to be demonstrated through implementation.

## 22. Resolved MVP compatibility decisions

The first supported profile is fixed to the locally supplied *Twister* 4.05 fixture (`twst_405.zip`) and its native dump (`twst_405.txt`). This is a compatibility anchor, not a restriction on the eventual runtime ROM-selection workflow.

| Area | MVP decision | Evidence / enforcement |
| --- | --- | --- |
| ROM fixture | `twst_405.zip`, SHA-256 `7419195A51F1295E9F928E0105326CBA3C4E32B9B2D3B59C004F773D132707A3` | Archive contains `twstcpu.405`, `twstdspa.400`, and the required sound ROMs. PinMAME audit remains an executable M0 check. |
| Dump fixture | `twst_405.txt`, SHA-256 `F711AEC5D42FDC423CA02BFD2C8F05C158AFAEE27A97ACDBF59D532B81095B11` | 14,443 timestamped frames; exactly 32 rows of 128 symbols per frame; symbols are limited to `0`-`3`. Timestamp units are profile data and must be verified, not assumed. |
| Initial format scope | 128x32, two-bit/four-shade monochrome DMD input only | Reject every other geometry, shade encoding, or delivery profile with a diagnostic until its independent parity profile passes. |
| Authoring authority | Pin the exact source commit and built binary of the original SerumColor ColorizingDMD editor at M0; use its real serializer and matcher as the compatibility oracle | Do not write the native project format independently before a create/open/save/export fixture passes. |
| Runtime authority | Build an isolated test worker from the same pinned legacy matching implementation used by the original-editor profile | PPUC libserum and libdmdutil are optional comparison/replay tools, not correctness authorities for this legacy profile. |
| Emulator baseline | Pin a stable PinMAME 3.6 Windows x64 binary/source pair, its SHA-256, and all launch flags at M0 | PinMAME 3.7 is pre-release and excluded from the baseline. Capture before display-oriented luminance/scaling transforms. |
| Grouping policy | Generalize only established numeric/text domains backed by renderer or domain evidence; keep observed-only and uncertain changes as separate references | No confidence threshold may silently convert an uncertain group into a generalized one. |
| Solver policy | Use strict-discrimination candidate-pool optimization with CP-SAT for the MVP | Report its bound only for the generated candidate pool and policy. Direct all-mask synthesis is deferred enhancement work. |
| Coverage claim | The 30-minute default run verifies and exports its captured scope only | Full-ROM coverage requires a separate reachability proof; observed saturation is never reported as complete coverage. |
| Support expansion | Add a driver/geometry profile only after the same ROM audit, raw-byte capture parity, native matching, editor round-trip, and replay fixture suite passes | The application accepts selected ROMs at runtime but reports unsupported profiles honestly. |

The former pending items are therefore executable completion criteria: byte-level capture parity, ordered matching parity, editor project round trip, inference accuracy, measured performance, and support-matrix expansion. They cannot truthfully be pre-declared as passing; M0-M8 must produce their recorded evidence before a release claim.


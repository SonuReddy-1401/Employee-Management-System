# Documentation Rules

1. Every number, version, date, name or result in any document must come from `docs/FACTS.md` and carry its id such as `[F-014]`.
2. If a fact is missing write `[NOT MEASURED]` or `[INPUT NEEDED]`, never guess.
3. Never invent features, results, quotations, references, people or dates.
4. Anything not verified is labeled "Hypothesis".
5. Limitations are stated plainly.
6. No marketing words (`robust`, `seamless`, `cutting-edge`, `state-of-the-art`, `blazing`, `effortless`).
7. Diagrams contain only components that exist in `docker-compose.yml`.
8. Code excerpts are copied verbatim with path and line numbers, at most 15 lines.
9. Never include passwords, tokens or secret values (environment variable NAMES are allowed).
10. Documents are written section by section: create the file with all headings first, then fill one section per step and print each section's word count.

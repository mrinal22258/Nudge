# Benchmark Traps Documentation

ResumeExtractBench includes three distinct "traps" commonly found in real resumes. These traps are designed to stress-test extraction pipelines and evaluate whether they possess the granularity and context awareness required for high-fidelity parsing.

## 1. Overlapping Date Ranges
- **Description**: The candidate has held multiple roles or attended schools with overlapping timeframes (e.g., working part-time/internships during university semesters or consulting on the side of a full-time position).
- **Challenge**: Naive extractors often get confused by simultaneous dates, assigning them to the wrong positions or truncating date durations.
- **Evaluation Criteria**: Check if `start_date` and `end_date` are correctly extracted and assigned for *both* overlapping roles without conflation.

## 2. Cross-Listed Projects
- **Description**: A major project is listed under both a "Projects" section and as a key achievement under "Work Experience".
- **Challenge**: Parsers frequently deduplicate this content or omit it from one of the fields due to schema-matching heuristics.
- **Evaluation Criteria**: Verify that the project appears *both* in the `experience[].bullets` (or experience context) and the `projects[]` list (conforming to the specific keys of the schema).

## 3. Embedded GitHub Links
- **Description**: GitHub usernames, repository paths, or pull request links are embedded inline inside descriptive text blocks rather than labeled in a dedicated header.
- **Challenge**: Pipelines that only parse headers or formal contact blocks miss links hidden in prose.
- **Evaluation Criteria**: The extractor must parse and populate `contact.links` and `open_source_contributions[].pr_link` by discovering URLs inside paragraphs.

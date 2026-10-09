# Who the public sector sponsors for permanent residence

## Why this file exists

Readers ask whether foreign nationals hold posts inside state government, in
public school districts, and at public universities. They do, the federal
government publishes the records, and until now this assistant answered that
the records did not exist. They do exist. This file says what is in them.

The page is `/public-sector-visas`. Send readers there for the detail.

## What the data is

PERM permanent labor certification disclosure files, published by the
Department of Labor's Office of Foreign Labor Certification. A PERM filing is
an employer asking the Department for permission to sponsor a named worker for
permanent residence, after testing the local labor market as the regulation
requires. A certified filing means the request was granted.

**The PERM file names the worker's citizenship and country of birth.** This is
the only federal disclosure file in this project that does. The H-1B LCA files
do not. If a reader asks about the nationality of workers in a specific job or
at a specific employer, PERM is where the answer is, and the window is
FY2013 to FY2024.

A certified filing is **not** a hire, not an admission, not a visa and not a
green card. It is permission to sponsor. Counting filings as people overstates
every figure.

## The window, and why it ends

Citizenship is published from FY2013. Country of birth from FY2015. Both stop
after FY2024: the Department removed every worker field from the FY2025 file,
which went from 155 columns to 137 and carries no citizenship, no country of
birth and no class of admission.

**The series has ended.** No future harvest brings it back. If a reader asks
for recent figures, say the disclosure stopped, not that the data is missing.

## The three sectors, and their headline totals

Employers are classified from the name they filed under. Membership is decided
by rule, so every count is a floor: an employer whose name does not say what it
is will not be found.

- **Universities and colleges**: 32,121 certified filings.
- **School districts and K-12 schools**: 7,804 certified filings.
- **Utilities, power, gas and water**: 2,821 certified filings.
- **State agencies**: 87 certified filings.

42,833 filings in total, FY2013 to FY2024. The employer count is per sector and must be fetched rather than added up here.

Utilities are found by industry code, not by name: "Electric" in a company
name usually means it makes equipment rather than power. Most of the sector
is investor-owned rather than public, and the page marks which is which
rather than dropping the private ones, because they run the same grid.

**Those are national figures and they are the only ones in this file.** Every
state figure must come from the `public_sector_by_state` tool. Quoting 87 as a
state's state-agency count is wrong for every state: most states have
none at all, and Washington, the state most often asked about, has six.

The sectors are different shapes and that is the finding. Universities are a
crowd: the ten busiest account for about a tenth of the sector. State agencies
are the opposite: ten bodies account for two thirds of 87 filings. A handful of
programs, not a general practice.

They also pay differently. School district filings have a median offered wage
near $47,700 and a tight distribution -- these are teachers. State agency
filings run far higher and are bimodal, because the sector is dominated by
psychiatrists in corrections and mental health.

## The tools

Two, and the choice between them matters more than usual here.

- `public_sector_overview` -- the national totals above, the three sectors,
  what each pays, and how many rows each anomaly test flagged.
- `public_sector_by_state` -- **one state**, with its own filings by sector,
  its top employers and citizenships, and every state-agency filing in that
  state listed whole: agency, job title, city, citizenship, country of birth,
  visa held, wage, decision date, and the federal file and case number.

Call `public_sector_by_state` whenever a question names a state, including
when it also asks something general. Anything by year, by state, by employer
or by citizenship must be fetched. Do not state a breakdown from memory and do
not reach for the national total when the state tool would answer.

## What a reader usually wants

Three questions come up, and the page answers each:

**Which agencies, and who filled the posts.** All 87 state-agency filings are
published whole on the page, with the agency, the job title, the city, the
worker's citizenship and country of birth, the visa held at the time of filing,
the wage offered, the decision date, and the federal file and case number each
came from. A reader can open the Department's own file and find the same line.

**One state.** The page carries a per-state breakdown for every state and
territory with a filing. An absence is a real result there: most states have no
state-agency filing at all, and the page says so rather than leaving a gap.

**The unexpected filings.** Four tests run over every row, not over rows chosen
in advance. They flag filings where the worker held something other than a work
visa; filings naming a US citizen, who cannot need a labor certification at
all; filings where citizenship and country of birth differ; and job titles
filed once in their whole sector. Each flagged row shows what flagged it.

> Guidance, not text to repeat: none of these tests finds wrongdoing, and a
> reader often assumes they do. Sponsoring a worker is lawful. The tests find
> rows that depart from the ordinary pattern, which is a different thing. Say
> so in your own words if the reader's question assumes otherwise, and never
> phrase it as instructions about how to read the site.

## One trap worth knowing

Most of the citizenship-and-birth mismatches are a single pattern: people who
emigrated once already, took a second nationality, and then moved again. The
largest single citizenship among them is Canada. That is a staging post, not a
discrepancy, and a reader who sees the raw count without the pattern will
read it as something it is not.

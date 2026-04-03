# PR-003 — Public participant entry by run slug

## Goal

Add a public run entry flow so participants join a concrete run by public slug.

## Why

Participant flow should start from a concrete run, not from an abstract experiment id.

## In scope

- add public run slug support
- add public participant entry path
- create participant sessions from run slug
- keep participant flow aligned with consent -> instructions -> practice -> 3 blocks -> questionnaires -> completion

## Out of scope

- resume flow
- final submit
- researcher auth
- deployment hardening

## Acceptance criteria

- a participant can enter a run using a public slug
- created session is attached to that run
- block flow still works
- docs updated
- tests updated

[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/DxqGQVx4)
# Project A&D – DBS  
## Politiek Inzicht Platform (Groep 8)

### Beschrijving
Ons platform geeft burgers een duidelijke en toegankelijke kijk op de politieke activiteit in het Vlaams Parlement.  
Gebruikers kunnen bekijken:
- welke volksvertegenwoordigers het meest actief zijn,  
- welke schriftelijke parlementaire vragen ze indienen,  
- rond welke thema’s deze vragen gaan, en  
- hoe snel ministers deze vragen beantwoorden.

Daarnaast kunnen burgers deze informatie binnenkort raadplegen per eigen kieskring, waardoor politieke inzichten persoonlijker en relevanter worden.  
Door versnipperde parlementaire data om te zetten in overzichtelijke visualisaties, maken we democratische informatie helder en toegankelijk voor iedereen.

### Live Platform
https://web-application-2025-group-8-a2qm.onrender.com/

### Kanbanbord
https://miro.com/app/board/uXjVJz4H2AQ=/

### Link to audio/video recording of feedback sessions with partner
eerste feedbackmoment: https://teams.microsoft.com/l/meetingrecap?driveId=b%21UEkwcKjidk2EEeaN2C7qunBTMPo_x8BDn8eqAOCma90Jl6xh4LFTSInb9WlbS4vZ&driveItemId=01WX7IDUH7NEFQX5U5QFELEI7QX342BYP7&sitePath=https%3A%2F%2Fugentbe-my.sharepoint.com%2F%3Av%3A%2Fg%2Fpersonal%2Floran_devriendt_ugent_be%2FEf9pCwv2nYFIsiPwvvmg4f8ByEG6xeFyAnu73xKg7-pmmQ&fileUrl=https%3A%2F%2Fugentbe-my.sharepoint.com%2Fpersonal%2Floran_devriendt_ugent_be%2FDocuments%2FOpnamen%2FAD%2520project-20251113_150225-Opname%2520van%2520vergadering.mp4%3Fweb%3D1&iCalUid=040000008200E00074C5B7101A82E0080000000023CADA1FEB53DC01000000000000000010000000B8BC7BDD6139ED458772B2D853004884&threadId=19%3Ameeting_NjZjOTY0MDgtNmMwMC00ZGIyLTk1ZGEtZmY4YmI4OWM2ZmQz%40thread.v2&organizerId=7b097fa6-897f-4d5d-ac78-ce69113069c0&tenantId=d7811cde-ecef-496c-8f91-a1786241b99c&callId=88d1cf65-106f-4f16-bf61-ecf23265ea33&threadType=meeting&meetingType=Scheduled&subType=RecapSharingLink_RecapCore

tweede feedbackmoment: https://teams.microsoft.com/l/meetingrecap?driveId=b%21UEkwcKjidk2EEeaN2C7qunBTMPo_x8BDn8eqAOCma90Jl6xh4LFTSInb9WlbS4vZ&driveItemId=01WX7IDUG26XHSGZE63NBK2GEOHUCN6W7Y&sitePath=https%3A%2F%2Fugentbe-my.sharepoint.com%2F%3Av%3A%2Fg%2Fpersonal%2Floran_devriendt_ugent_be%2FEdr1zyNknttCrRiOPQTfW_gBEHUDx6teZCTwEB7EYOodoA&fileUrl=https%3A%2F%2Fugentbe-my.sharepoint.com%2Fpersonal%2Floran_devriendt_ugent_be%2FDocuments%2FOpnamen%2FAD%2520project2-20251201_100343-Opname%2520van%2520vergadering.mp4%3Fweb%3D1&iCalUid=040000008200E00074C5B7101A82E00800000000294F9F5AFD5EDC0100000000000000001000000046BC0D21793EC442B8997E78FECF3557&threadId=19%3Ameeting_NTM2YmNhMGEtZDQyNy00ZDk5LThiNzEtZjI4NTcyNzI4ZjAw%40thread.v2&organizerId=7b097fa6-897f-4d5d-ac78-ce69113069c0&tenantId=d7811cde-ecef-496c-8f91-a1786241b99c&callId=c7a296b8-54f7-462f-892d-4ebfc4484b88&threadType=meeting&meetingType=Scheduled&subType=RecapSharingLink_RecapCore

### Link to UI prototype
https://lovable.dev/projects/423033f1-cd55-4120-af69-54792385afd1?permissionView=main
see image.png for screenshot prototype

### DDL
-- Nodig voor UUID-generatie
create extension if not exists pgcrypto;

-- ===== ENUMS =====
do $$
begin
  if not exists (select 1 from pg_type where typname = 'geslacht_enum') then
    create type geslacht_enum as enum ('M', 'V', 'X');
  end if;
end$$;

-- ===== Fractie =====
create table if not exists public.fractie (
  id       uuid primary key,                 -- UUID wordt aangeleverd via API of script
  naam     text not null,
  logo_url text
);

-- ===== Functies =====
create table if not exists public.functies (
  id           uuid primary key,             -- geen default, ID komt uit script of API
  code         text not null unique,
  naam         text not null,
  omschrijving text
);

-- ===== Persoon =====
create table if not exists public.persoon (
  id             uuid primary key,            -- id = uuidvv uit API
  voornaam       text not null,
  naam           text not null,
  geboortedatum  date,
  geslacht       geslacht_enum,
  roepnaam       text,
  kieskring      text not null
);

-- ===== Persoonfunctie =====
create table if not exists public.persoonfunctie (
  id     uuid primary key,                    -- zelfde reden, script levert ID
  id_fnc uuid not null references public.functies (id) on update cascade on delete restrict,
  id_prs uuid not null references public.persoon  (id) on update cascade on delete cascade,
  van    date not null,
  tot    date,
  id_frc uuid references public.fractie (id) on update cascade on delete restrict
);

-- ===== Thema =====
create table if not exists public.thema (
  id           uuid primary key,
  naam         text not null,
  omschrijving text
);

-- ===== SchriftelijkeVragen =====
create table if not exists public.schriftelijke_vragen (
  id            uuid primary key,
  ingediend     date not null,
  onderwerp     text not null,
  tekst         text,
  id_prsfnc_vs  uuid not null references public.persoonfunctie (id) on update cascade on delete restrict,
  id_prsfnc_min uuid not null references public.persoonfunctie (id) on update cascade on delete restrict,
  beantwoord    date
);

-- ===== ThemaKoppeling =====
create table if not exists public.thema_koppeling (
  id      uuid primary key,
  id_thm  uuid not null references public.thema (id) on update cascade on delete cascade,
  id_schv uuid not null references public.schriftelijke_vragen (id) on update cascade on delete cascade,
  unique (id_thm, id_schv)
);

-- ===== Indexen =====
create index if not exists idx_pf_prs on public.persoonfunctie (id_prs);
create index if not exists idx_pf_fnc on public.persoonfunctie (id_fnc);
create index if not exists idx_pf_frc on public.persoonfunctie (id_frc);

create index if not exists idx_schv_vs  on public.schriftelijke_vragen (id_prsfnc_vs);
create index if not exists idx_schv_min on public.schriftelijke_vragen (id_prsfnc_min);

create index if not exists idx_thmkpl_schv on public.thema_koppeling (id_schv);
create index if not exists idx_thmkpl_thm  on public.thema_koppeling (id_thm);


### DEMO VIDEO

https://1drv.ms/v/c/316adbab80b3b2e9/IQAuQpCg4o7pToAh4oXU8AprAbDS8fninfyfXWiznnZshIE

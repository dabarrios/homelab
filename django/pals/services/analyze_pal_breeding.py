import csv
import json
from collections import defaultdict, Counter
from pathlib import Path

WORK = Path('/mnt/c/Users/David/AppData/Local/Temp/palworld_breeding_readonly_303_2026')
ASSETS = Path('/mnt/c/Users/David/AppData/Local/Temp/palworld_parser_tools/palworld-server-tool/web/src/assets')
OUT_ROSTER = WORK / 'pal_roster.csv'
OUT_PASSIVES = WORK / 'passive_inventory.csv'
OUT_REPORT = WORK / 'breeding_report.md'

ZERO = '00000000-0000-0000-0000-000000000000'
TARGET_IDS = {'IceHorse', 'BOSS_IceHorse'}

pal_names = json.load(open(ASSETS / 'pal.json', encoding='utf-8')).get('en', {})
skill_names = json.load(open(ASSETS / 'skill.json', encoding='utf-8')).get('en', {})

def skill_name(pid):
    return skill_names.get(pid, {}).get('name') or pid

def pal_name(cid):
    return pal_names.get(cid) or cid

def prop_value(obj, default=None):
    if not isinstance(obj, dict) or 'value' not in obj:
        return default
    v = obj['value']
    if isinstance(v, dict) and set(v.keys()) >= {'type', 'value'}:
        return v.get('value')
    return v

def get_field(sp, key, default=None):
    return prop_value(sp.get(key), default)

def get_guid_struct(prop):
    try:
        return prop['value']['ID']['value']
    except Exception:
        return None

def get_skills(sp):
    try:
        vals = sp['PassiveSkillList']['value']['values']
        return [x for x in vals if x]
    except Exception:
        return []

def get_char_id(sp):
    return get_field(sp, 'CharacterID')

def get_bool(sp, key):
    v = get_field(sp, key)
    return bool(v)

def get_int(sp, key, default=0):
    v = get_field(sp, key, default)
    try:
        return int(v)
    except Exception:
        return default

def norm_guid(g):
    return str(g).lower() if g else ''

# Player names and their party / storage containers.
players = {}
for pl in json.load(open(WORK / 'structure.json', encoding='utf-8')).get('players', []):
    try:
        first = f'{int(pl["player_uid"]):08x}'
        guid = f'{first}-0000-0000-0000-000000000000'
        players[norm_guid(guid)] = pl.get('nickname') or guid
    except Exception:
        pass

container_labels = {}
for pjson in sorted((WORK / 'Players').glob('*.json')):
    data = json.load(open(pjson, encoding='utf-8'))
    sd = data.get('properties', {}).get('SaveData', {}).get('value', {})
    uid = pjson.stem.lower()
    guid = f'{uid[:8]}-{uid[8:12]}-{uid[12:16]}-{uid[16:20]}-{uid[20:32]}'
    nickname = players.get(norm_guid(guid), pjson.stem)
    party = get_guid_struct(sd.get('OtomoCharacterContainerId'))
    storage = get_guid_struct(sd.get('PalStorageContainerId'))
    if party:
        container_labels[norm_guid(party)] = f'Party ({nickname})'
    if storage:
        # Some low-population player saves have only a 5-slot storage-like container; keep the game field name explicit.
        container_labels[norm_guid(storage)] = f'Palbox/Storage ({nickname})'

level = json.load(open(WORK / 'Level.full.json', encoding='utf-8'))
ws = level['properties']['worldSaveData']['value']

def save_to_map_coords(loc):
    data_x = float(loc.get('x', 0) or 0)
    data_y = float(loc.get('y', 0) or 0)
    return ((data_y - 158000) / 459, (data_x + 123888) / 459)

# Base worker containers.
base_locs = {}
for idx, e in enumerate(ws.get('BaseCampSaveData', {}).get('value', []), 1):
    raw = e['value']['WorkerDirector']['value']['RawData']['value']
    cid = raw.get('container_id')
    loc = raw.get('spawn_transform', {}).get('translation', {})
    loc_txt = ''
    if loc:
        map_x, map_y = save_to_map_coords(loc)
        loc_txt = f" @ ({map_x:.0f}, {map_y:.0f})"
    if cid:
        label = f'Base {idx}{loc_txt}'
        container_labels[norm_guid(cid)] = label
        base_locs[norm_guid(cid)] = label

# Instance -> container location.
instance_locations = {}
for c in ws.get('CharacterContainerSaveData', {}).get('value', []):
    key = c.get('key')
    if isinstance(key, dict):
        cid = key.get('ID', {}).get('value')
    else:
        cid = key
    cidn = norm_guid(cid)
    label = container_labels.get(cidn, f'Unknown container {cid}')
    slots = c['value']['Slots']['value']['values']
    for s in slots:
        rd = s['RawData']['value']
        iid = norm_guid(rd.get('instance_id'))
        if iid and iid != ZERO:
            slot = s['SlotIndex']['value']
            instance_locations[iid] = f'{label}, slot {slot}'

roster = []

def owner_from_base_metadata(sp, location):
    if not location.startswith('Base '):
        return '', ''
    modifier = norm_guid(get_field(sp, 'LastNickNameModifierPlayerUid'))
    if modifier in players:
        return modifier, players[modifier]
    return '', ''

owned_player_uids = set(players.keys())
for e in ws.get('CharacterSaveParameterMap', {}).get('value', []):
    key = e['key']
    player_uid = norm_guid(key.get('PlayerUId', {}).get('value'))
    instance_id = norm_guid(key.get('InstanceId', {}).get('value'))
    sp = e['value']['RawData']['value']['object']['SaveParameter']['value']
    cid = get_char_id(sp)
    if not cid or cid == 'None' or get_bool(sp, 'IsPlayer'):
        continue
    owner = norm_guid(get_field(sp, 'OwnerPlayerUId'))
    location = instance_locations.get(instance_id, 'Owned, no current container slot found')
    owner_name = players.get(owner, owner)
    ownership_basis = 'OwnerPlayerUId'
    if owner not in owned_player_uids:
        inferred_owner, inferred_name = owner_from_base_metadata(sp, location)
        if inferred_owner:
            owner = inferred_owner
            owner_name = inferred_name
            ownership_basis = 'Base LastNickNameModifierPlayerUid'
        else:
            continue
    skills = get_skills(sp)
    rank_raw = get_int(sp, 'Rank', 1)
    row = {
        'source': 'Level.sav',
        'owner': owner_name,
        'owner_uid': owner,
        'ownership_basis': ownership_basis,
        'player_uid': player_uid,
        'instance_id': instance_id,
        'species_id': cid,
        'species': pal_name(cid),
        'nickname': get_field(sp, 'NickName', '') or '',
        'level': get_int(sp, 'Level', 0),
        'gender': str(get_field(sp, 'Gender', '')).replace('EPalGenderType::', ''),
        'passive_ids': ';'.join(skills),
        'passives': ';'.join(skill_name(x) for x in skills),
        'hp_iv': get_int(sp, 'Talent_HP', 0),
        'attack_iv': get_int(sp, 'Talent_Shot', 0),
        'defense_iv': get_int(sp, 'Talent_Defense', 0),
        'rank_raw': rank_raw,
        'condensation_stars': max(0, rank_raw - 1),
        'location': location,
        'is_lucky': get_bool(sp, 'IsRarePal'),
        'is_boss': cid.startswith('BOSS_'),
    }
    roster.append(row)

# DPS is empty in this save as decoded, but keep this path active for future reproducibility.
dps = json.load(open(WORK / 'dps.json', encoding='utf-8'))
dps_added = 0
for i, e in enumerate(dps['properties']['SaveParameterArray']['value']['values']):
    sp = e['SaveParameter']['value']
    cid = get_char_id(sp)
    if not cid or cid == 'None' or get_bool(sp, 'IsPlayer'):
        continue
    owner = norm_guid(get_field(sp, 'OwnerPlayerUId'))
    skills = get_skills(sp)
    rank_raw = get_int(sp, 'Rank', 1)
    roster.append({
        'source': 'DPS _dps.sav',
        'owner': players.get(owner, owner),
        'owner_uid': owner,
        'ownership_basis': 'OwnerPlayerUId',
        'player_uid': '',
        'instance_id': f'dps-slot-{i}',
        'species_id': cid,
        'species': pal_name(cid),
        'nickname': get_field(sp, 'NickName', '') or '',
        'level': get_int(sp, 'Level', 0),
        'gender': str(get_field(sp, 'Gender', '')).replace('EPalGenderType::', ''),
        'passive_ids': ';'.join(skills),
        'passives': ';'.join(skill_name(x) for x in skills),
        'hp_iv': get_int(sp, 'Talent_HP', 0),
        'attack_iv': get_int(sp, 'Talent_Shot', 0),
        'defense_iv': get_int(sp, 'Talent_Defense', 0),
        'rank_raw': rank_raw,
        'condensation_stars': max(0, rank_raw - 1),
        'location': f'Dimensional Pal Storage, slot {i}',
        'is_lucky': get_bool(sp, 'IsRarePal'),
        'is_boss': cid.startswith('BOSS_'),
    })
    dps_added += 1

# Deduplicate by instance/source slot.
seen = set(); deduped = []
for r in roster:
    key = (r['source'], r['instance_id'])
    if key not in seen:
        seen.add(key); deduped.append(r)
roster = deduped

fieldnames = ['source','owner','owner_uid','ownership_basis','player_uid','instance_id','species_id','species','nickname','level','gender','passive_ids','passives','hp_iv','attack_iv','defense_iv','rank_raw','condensation_stars','location','is_lucky','is_boss']
with open(OUT_ROSTER, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader(); w.writerows(roster)

passive_to_pals = defaultdict(list)
for r in roster:
    ids = [x for x in r['passive_ids'].split(';') if x]
    names = [x for x in r['passives'].split(';') if x]
    for pid, pname in zip(ids, names):
        label = f"{r['species']} {('['+r['nickname']+']') if r['nickname'] else ''} L{r['level']} {r['gender']} IV {r['hp_iv']}/{r['attack_iv']}/{r['defense_iv']} - {r['location']}"
        passive_to_pals[pid].append(label)

with open(OUT_PASSIVES, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=['passive_id','passive_name','count','pals'])
    w.writeheader()
    for pid in sorted(passive_to_pals, key=lambda x: skill_name(x)):
        vals = passive_to_pals[pid]
        w.writerow({'passive_id': pid, 'passive_name': skill_name(pid), 'count': len(vals), 'pals': ' | '.join(vals)})

# Report helpers.
def pal_label(r):
    nick = f" [{r['nickname']}]" if r['nickname'] else ''
    return f"{r['species']}{nick} L{r['level']} {r['gender']} IV {r['hp_iv']}/{r['attack_iv']}/{r['defense_iv']} stars {r['condensation_stars']} - {r['location']}"

def has_passive(r, name_or_id):
    ids = set(r['passive_ids'].split(';')) if r['passive_ids'] else set()
    names = set(r['passives'].split(';')) if r['passives'] else set()
    return name_or_id in ids or name_or_id in names

high_value_names = [
    'Legend','Swift','Runner','Nimble','Serenity','Impatient','Eternal Engine','Demon God','Musclehead',
    'Dimensional Leap','God of Destruction','Diamond Body','Lucky','Vampiric','King of the Waves',
    'Siren of the Void','Eternal Flame','Invader','Lunker','Zen Mind','Earth Emperor','Lord of Lightning',
    'Flame Emperor','Celestial Emperor','Lord of the Sea','Ice Emperor','Lord of the Underworld','Divine Dragon',
]
high_ids = [pid for pid,meta in skill_names.items() if meta.get('name') in high_value_names]
# Include generic high-value categories from descriptions.
for pid, meta in skill_names.items():
    desc = meta.get('desc','')
    nm = meta.get('name','')
    if any(tok in desc for tok in ['Attack +30', 'Attack +20', 'Movement Speed', 'movement speed', 'cooldown', 'Defense +30', 'Max stamina']):
        if pid not in high_ids:
            high_ids.append(pid)

frost = [r for r in roster if r['species_id'] in TARGET_IDS]
# For a normal Frostallion child, current 1.0 breeding data says Frostallion x Frostallion only.
frost_available_ids = sorted({pid for r in frost for pid in r['passive_ids'].split(';') if pid}, key=lambda p: skill_name(p))

# Desired scoring for general-purpose ride + combat.
priority = {
    'Legend': 100,
    'MoveSpeed_up_3': 95,
    'WorldTree_MoveSpeed': 92,
    'Stamina_Up_3': 88,
    'CoolTimeReduction_Up_1': 86,
    'CoolTimeReduction_Up_2': 84,
    'PAL_ALLAttack_up3': 82,
    'MoveSpeed_up_2': 78,
    'MoveSpeed_up_1': 65,
    'Deffence_up3': 58,
    'Rare': 55,
    'PAL_ALLAttack_up2': 50,
    'Attack_up2': 48,
}
def score_pid(pid):
    return priority.get(pid, 0) + (10 if 'ElementBoost_Ice' in pid else 0)

breedable_now = sorted(frost_available_ids, key=lambda p: (-score_pid(p), skill_name(p)))
best_build = breedable_now[:4]

all_available_names = {skill_name(pid): pid for pid in passive_to_pals}
unavailable = []
for wanted in ['Eternal Engine','Demon God','Dimensional Leap','Serenity','Swift','Runner','Nimble','Legend','Musclehead']:
    if wanted not in all_available_names:
        unavailable.append(wanted)

# Donors: best owned pals carrying desired passives, with Frostallion donors separated.
desired_ids = set(best_build) | {pid for pid in passive_to_pals if skill_name(pid) in ['Legend','Swift','Runner','Nimble','Serenity','Eternal Engine','Demon God','Musclehead','Dimensional Leap']}
def donor_score(r):
    ids = [pid for pid in r['passive_ids'].split(';') if pid]
    return sum(score_pid(pid) for pid in ids) + r['attack_iv'] + r['hp_iv']*0.2 + r['defense_iv']*0.2 - max(0, len(ids)-4)*5
best_donors = sorted([r for r in roster if any(pid in desired_ids for pid in r['passive_ids'].split(';') if pid)], key=donor_score, reverse=True)[:25]
frost_donors = sorted(frost, key=donor_score, reverse=True)

lines = []
lines.append('# Palworld Breeding Read-Only Report')
lines.append('')
lines.append(f'- Decoded owned Level/normal player Pals: {len([r for r in roster if r["source"] == "Level.sav"])}')
lines.append(f'- Decoded non-empty Dimensional Pal Storage Pals: {dps_added} (the `_dps.sav` exists but all 9,600 decoded slots are empty)')
lines.append(f'- Total owned Pals in roster CSV: {len(roster)}')
lines.append(f'- Unique passive skills owned: {len(passive_to_pals)}')
lines.append('')
lines.append('## AVAILABLE HIGH-VALUE PASSIVES')
for pid in high_ids:
    if pid in passive_to_pals:
        vals = passive_to_pals[pid]
        sample = '; '.join(vals[:8]) + (f'; +{len(vals)-8} more' if len(vals) > 8 else '')
        lines.append(f'- {skill_name(pid)} (`{pid}`): {sample}')
lines.append('')
lines.append('## BEST FROSTALLION BUILD AVAILABLE NOW')
if len(frost) < 2:
    lines.append('- Not breedable now: fewer than two Frostallion are present.')
elif best_build:
    for pid in best_build:
        lines.append(f'- {skill_name(pid)} (`{pid}`)')
    if len(best_build) < 4:
        lines.append(f'- Open slot(s): only {len(best_build)} desired/passive options are currently present on owned Frostallion parents.')
    lines.append('')
    lines.append('Reasoning: Palworld 1.0 Frostallion is same-species only for producing Frostallion, so the immediately breedable pool is limited to passives already on your current Frostallion. This build prioritizes ride speed first, then broad combat value and cooldown/stamina if present.')
else:
    lines.append('- No passive-bearing Frostallion donors found. You can breed Frostallion x Frostallion, but current Frostallion passives do not contain the requested movement/combat targets.')
lines.append('')
lines.append('## BEST PASSIVE DONORS')
lines.append('Frostallion-compatible donors for a Frostallion child:')
if frost_donors:
    for r in frost_donors[:12]:
        lines.append(f'- {pal_label(r)} - passives: {r["passives"] or "none"}')
else:
    lines.append('- None found.')
lines.append('')
lines.append('Other owned high-value passive holders (useful for other projects, but not direct Frostallion parents in 1.0):')
for r in best_donors[:15]:
    if r in frost_donors:
        continue
    lines.append(f'- {pal_label(r)} - passives: {r["passives"] or "none"}')
lines.append('')
lines.append('## BREEDING PLAN')
if len(frost) >= 2:
    usable = frost_donors[:2]
    lines.append('1. Breed Frostallion + Frostallion. In Palworld 1.0 this is the only normal pairing that produces Frostallion.')
    if len(usable) >= 2:
        lines.append(f'2. Start with: {pal_label(usable[0])}')
        lines.append(f'3. Pair with: {pal_label(usable[1])}')
        lines.append('4. Keep offspring that inherit the target passives; use clean/low-junk Frostallion offspring as consolidation parents until the final 4-passive result appears.')
    else:
        lines.append('2. You have only one Frostallion donor record available after filtering, so a complete pair was not found.')
    non_frost_desired = [r for r in best_donors if r not in frost_donors]
    if non_frost_desired:
        lines.append('')
        lines.append('Note: passives on non-Frostallion Pals cannot be chained into normal Frostallion under current 1.0 breeding data, because Frostallion only breeds true from Frostallion + Frostallion.')
else:
    lines.append('1. Catch or otherwise obtain at least two Frostallion first.')
    lines.append('2. Then breed Frostallion + Frostallion; mixed parent chains are not available for normal Frostallion in 1.0.')
lines.append('')
lines.append('## CURRENT FROSTALLION')
if frost:
    for r in frost:
        lines.append(f'- {pal_label(r)} - passives: {r["passives"] or "none"}')
else:
    lines.append('- None found.')
lines.append('')
lines.append('## SPECIFIC PASSIVE CHECK')
for wanted in ['Legend','Swift','Runner','Nimble','Serenity','Musclehead','Eternal Engine','Demon God']:
    pid = all_available_names.get(wanted)
    if pid:
        lines.append(f'- {wanted}: YES - {len(passive_to_pals[pid])} Pal(s)')
    else:
        lines.append(f'- {wanted}: no')
lines.append('')
lines.append('## UNAVAILABLE BUT WORTH WATCHING FOR')
for wanted in unavailable:
    lines.append(f'- {wanted}')
if not unavailable:
    lines.append('- None of the explicitly requested top passives are fully absent from the save.')
lines.append('')
lines.append('## REPRODUCIBLE COMMANDS')
lines.append('```powershell')
lines.append("git clone https://github.com/zaigie/palworld-server-tool.git $env:TEMP\\palworld_parser_tools\\palworld-server-tool")
lines.append("git clone https://github.com/CyrixJD115/PalSav.git $env:TEMP\\palworld_parser_tools\\PalSav")
lines.append("# In the temp PalSav/palooz/setup.py copy, use MSVC flags on Windows; WSL build used gcc instead.")
lines.append("wsl bash -lc 'cd /mnt/c/Users/David/AppData/Local/Temp/palworld_parser_tools && python3 -m venv .wsl-venv && . .wsl-venv/bin/activate && python -m pip install --upgrade pip setuptools wheel && python -m pip install ./PalSav/palooz && python -m pip install -e ./PalSav orjson'")
lines.append("wsl bash -lc 'cd /mnt/c/Users/David/AppData/Local/Temp/palworld_parser_tools && . .wsl-venv/bin/activate && python3 palworld-server-tool/sav_cli/sav_cli.py -f /mnt/c/Users/David/AppData/Local/Temp/palworld_breeding_readonly_303_2026/Level.sav -o /mnt/c/Users/David/AppData/Local/Temp/palworld_breeding_readonly_303_2026/structure.json --verbose'")
lines.append("wsl bash -lc 'cd /mnt/c/Users/David/AppData/Local/Temp/palworld_parser_tools && . .wsl-venv/bin/activate && palsav convert /mnt/c/Users/David/AppData/Local/Temp/palworld_breeding_readonly_303_2026/Level.sav --to-json -o /mnt/c/Users/David/AppData/Local/Temp/palworld_breeding_readonly_303_2026/Level.full.json --force'")
lines.append("wsl bash -lc 'cd /mnt/c/Users/David/AppData/Local/Temp/palworld_parser_tools && . .wsl-venv/bin/activate && palsav convert /mnt/c/Users/David/AppData/Local/Temp/palworld_breeding_readonly_303_2026/Players/D8C1CFBD000000000000000000000000_dps.sav --to-json -o /mnt/c/Users/David/AppData/Local/Temp/palworld_breeding_readonly_303_2026/dps.json --force'")
lines.append('```')

OUT_REPORT.write_text('\n'.join(lines) + '\n', encoding='utf-8')
print(f'wrote {OUT_ROSTER}')
print(f'wrote {OUT_PASSIVES}')
print(f'wrote {OUT_REPORT}')
print(f'roster={len(roster)} passives={len(passive_to_pals)} frost={len(frost)} dps_added={dps_added}')

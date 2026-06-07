#!/usr/bin/env python3
"""Insert the new sheets, charms and bracelets into catalog.js.

Idempotent-ish: it operates on anchor strings in catalog.js. Run once on the
original 5-sheet catalog. Re-running will refuse if markers are already present.
"""
import re, io

SHEET_LINES = {
    6: ('charms/sheet-6-vintage-miniatures.jpeg', 'Vintage Everyday Miniatures'),
    7: ('charms/sheet-7-retro-childhood.jpeg', 'Retro Childhood Whimsy'),
    8: ('charms/sheet-8-teacup-critters.jpeg', 'Teacup Cozy Critters'),
    9: ('charms/sheet-9-sweetheart.jpeg', 'Sweetheart Gallery'),
}

# (id, name, emoji, sheet, pos, category, meaning, tags)
CHARMS = [
 # ---- Sheet 6 — Vintage Everyday Miniatures ----
 ("red-apple","Red Apple","🍎",6,"1,1","fruit","temptation, teachers, the everyday",["apple","fruit","red","teacher","school","health","orchard","autumn","everyday","simple"]),
 ("green-sardine-oval","Green Sardine Tin","🐟",6,"1,2","sea","Mediterranean tables, simple pleasures",["sardine","fish","tin","mediterranean","food","sea","vintage","catch","coastal"]),
 ("tulip-checker","Checkerboard Tulip","🌷",6,"1,3","flora","playful spring, a bold bloom",["tulip","flower","checker","checkerboard","spring","bloom","bold","retro","garden"]),
 ("sardine-tin-red","Red Sardine Tin","🐟",6,"1,4","sea","seaside markets, quirky taste",["sardine","fish","tin","red","food","sea","mediterranean","quirky","vintage"]),
 ("blue-scallop-oval","Blue Scallop","🐚",6,"1,5","sea","the shore, calm waters",["scallop","shell","sea","blue","wave","ocean","beach","coastal","delft","calm"]),
 ("purple-tulip-oval","Purple Tulip","🌷",6,"2,1","flora","grace, springtime, first love",["tulip","flower","purple","spring","bloom","grace","garden","romance","gentle"]),
 ("pink-daisy-oval","Pink Daisy","🌸",6,"2,2","flora","cheerful innocence, simple joy",["daisy","flower","pink","cheerful","innocence","joy","spring","simple","bloom"]),
 ("red-heart-round","Folk Heart","❤️",6,"2,3","love","open-hearted love",["heart","love","red","folk","romance","valentine","affection","warm","sweetheart"]),
 ("stars-fish-card","Stars & Fish","⭐",6,"2,4","sea","wishes, the deep, a bit of magic",["star","stars","fish","sea","wish","magic","night","ocean","dream","whimsy"]),
 ("violet-flower-oval","Violet Bloom","🌼",6,"2,5","flora","modesty, quiet devotion",["violet","flower","purple","bloom","devotion","gentle","spring","garden","modest"]),
 ("strawberry-stripe-oval","Striped Strawberry","🍓",6,"2,6","fruit","summer sweetness, first crushes",["strawberry","fruit","berry","summer","sweet","red","pink","picnic","crush","garden"]),
 ("pumpkin-square","Little Pumpkin","🎃",6,"3,1","flora","autumn, harvest, cosy season",["pumpkin","autumn","fall","harvest","orange","halloween","cosy","squash","october"]),
 ("blue-fish-green","Blue Fish","🐟",6,"3,2","sea","going your own way, the catch",["fish","blue","sea","ocean","swim","catch","water","freedom","individual"]),
 ("three-sardines","Three Sardines","🐟",6,"3,3","sea","good company, the shoal",["sardine","fish","three","sea","shoal","together","company","ocean","mediterranean","family"]),
 ("green-fish-tall","Green Fish","🐠",6,"3,4","sea","swim against the current",["fish","green","sea","ocean","swim","bold","water","individual","catch"]),
 ("cat-square","Folk Cat","🐱",6,"3,5","animal","independence, cosy company",["cat","kitty","animal","pet","independent","cosy","companion","feline","home"]),
 ("mushroom-square","Toadstool","🍄",6,"3,6","folk","fairy-tale luck, woodland magic",["mushroom","toadstool","fairy","woodland","magic","luck","forest","whimsy","cottagecore"]),
 ("sun-navy-square","Folk Sun","☀️",6,"4,1","celestial","optimism, a new day",["sun","sunshine","optimism","warm","day","bright","hope","folk","radiant","happy"]),
 ("clouds-oval","Clouds","☁️",6,"4,2","celestial","daydreams, blue skies ahead",["cloud","clouds","sky","daydream","dream","calm","blue","weather","peace","hope"]),
 ("tree-landscape","Little Tree","🌳",6,"4,3","nature","growth, roots, the seasons",["tree","nature","growth","roots","landscape","seasons","grounded","green","life","outdoors"]),
 ("tulip-dots-round","Dotted Tulip","🌷",6,"4,4","flora","cheer, a handpicked bloom",["tulip","flower","red","dots","spring","cheer","bloom","garden","folk"]),
 ("flower-lavender-round","Lavender Bloom","💜",6,"4,5","flora","calm, healing, quiet",["flower","lavender","purple","calm","healing","soothe","gentle","spring","bloom","peace"]),
 ("confetti-oval","Confetti Bloom","🎉",6,"4,6","folk","celebration, a joyful mess",["confetti","celebrate","party","joy","festive","terracotta","folk","flowers","happy","colourful"]),
 ("strawberry-blue-oval","Strawberry (Blue Stripe)","🍓",6,"5,1","fruit","summer picnics, sweetness",["strawberry","berry","fruit","summer","picnic","sweet","blue","garden"]),
 ("pear-oval","Green Pear","🍐",6,"5,2","fruit","patience, autumn orchards",["pear","fruit","green","autumn","orchard","patience","harvest","sweet","garden"]),
 ("cherries-square","Cherries","🍒",6,"5,3","fruit","sweethearts, summer, pairs",["cherry","cherries","fruit","red","summer","sweet","pair","couple","love","picnic"]),
 ("gingham-bow-oval","Gingham Bow","🎀",6,"5,4","object","picnics, sweetness, a pretty wrap",["bow","gingham","ribbon","picnic","sweet","gift","blue","country","pretty","charming"]),
 ("red-house-oval","Little Red House","🏠",6,"5,5","home","home, belonging, a fresh start",["house","home","belonging","family","cottage","move","new home","shelter","roots"]),
 ("sardine-tin-yellow","Yellow Sardine Tin","🐟",6,"5,6","sea","retro kitchens, simple feasts",["sardine","fish","tin","yellow","food","retro","kitchen","sea","mediterranean"]),
 # ---- Sheet 7 — Retro Childhood Whimsy ----
 ("evil-eye-heart","Evil-Eye Heart","🧿",7,"1,1","luck","protection, watchful love",["eye","evil eye","heart","protection","luck","amulet","love","ward","guard"]),
 ("mash-notebook","MASH Notebook","📓",7,"1,2","childhood","school days, daydreamed futures",["notebook","school","mash","game","childhood","nostalgia","paper","write","memories","classroom"]),
 ("handheld-game","Handheld Game","🎮",7,"1,3","childhood","90s play, pure fun",["game","gameboy","handheld","retro","90s","play","fun","childhood","nostalgia","gamer"]),
 ("mountain-oval","Blue Mountain","🏔️",7,"1,4","nature","adventure, the climb",["mountain","adventure","outdoors","climb","nature","travel","hike","summit","explore"]),
 ("retro-disc","Retro Disc","💿",7,"1,5","music","mixtapes, nostalgia, your jam",["disc","cd","record","music","retro","nostalgia","90s","mixtape","vintage"]),
 ("flower-lock","Flower Lock","🔒",7,"2,1","object","secrets kept, first diaries",["lock","key","secret","diary","childhood","heart","protect","keepsake","flowers"]),
 ("blue-village-oval","Blue Village","🏘️",7,"2,2","home","hometown, where you're from",["village","town","home","houses","blue","hometown","roots","delft","community"]),
 ("pink-purse-heart","Pink Treasure Purse","👛",7,"2,3","childhood","little treasures, girlhood",["purse","bag","pink","heart","treasure","girlhood","childhood","cute","keepsake"]),
 ("ty-heart","'ty' Heart","🧸",7,"2,4","childhood","beanie babies, collected joys",["heart","ty","beanie","toy","childhood","nostalgia","collect","90s","red","plush"]),
 ("gingerbread-man","Gingerbread Man","🍪",7,"2,5","food","baking days, holiday warmth",["gingerbread","cookie","baking","holiday","christmas","sweet","warm","kitchen","festive"]),
 ("blue-sun-oval","Blue Sun","☀️",7,"3,1","celestial","calm optimism",["sun","blue","optimism","calm","day","bright","hope","celestial","warm"]),
 ("green-label-oval","Retro Label","🥫",7,"3,2","object","vintage pantry, nostalgia",["label","can","retro","vintage","pantry","green","nostalgia","kitchen"]),
 ("sun-square","Sunny Day","🌞",7,"3,3","celestial","happiness, warmth, summer",["sun","sunshine","happy","warm","summer","bright","day","optimism","joy"]),
 ("sunscreen-can","Sunscreen","🧴",7,"3,4","sea","beach days, summer holidays",["sunscreen","beach","summer","holiday","sea","vacation","sun","coast","tropical"]),
 ("tomato-can","Tomato Tin","🍅",7,"3,5","food","home cooking, nonna's kitchen",["tomato","can","food","cooking","kitchen","italian","nonna","pantry","sauce","home"]),
 ("blue-bottle","Little Bottle","🧴",7,"3,6","object","potions, keeping it together",["bottle","potion","retro","blue","vintage","apothecary","remedy"]),
 ("soap-bar","Soap Bar","🧼",7,"3,7","object","fresh starts, clean slates",["soap","clean","fresh","start","green","retro","bath","renew"]),
 ("yellow-flower-square","Yellow Bloom","🌼",7,"4,1","flora","friendship, sunny days",["flower","yellow","friendship","sunny","cheer","bloom","spring","happy","daisy"]),
 ("pink-cat-oval","Pink Cat","🐱",7,"4,2","animal","playful, a little wild",["cat","kitty","pink","animal","pet","playful","cute","feline","companion"]),
 ("blue-swirl-round","Blue Swirl","🌀",7,"4,3","object","peace, going with the flow",["swirl","spiral","blue","peace","calm","flow","retro","abstract"]),
 ("roses-oval","Roses","🌹",7,"4,4","flora","romance, timeless love",["rose","roses","flower","love","romance","pink","timeless","bouquet","valentine","beauty"]),
 ("snake-oval","Garden Snake","🐍",7,"4,5","animal","transformation, renewal",["snake","serpent","transformation","renewal","green","wild","nature","change"]),
 ("striped-totem","Striped Totem","🎏",7,"4,6","folk","play, bold colour, individuality",["totem","stripe","folk","bold","colour","playful","art","individual","quirky"]),
 # ---- Sheet 8 — Teacup Cozy Critters ----
 ("teacup-bear","Teacup Bear & Bunny","🐻",8,"1,1","animal","cosy comfort, gentle friendship",["bear","bunny","teacup","cosy","comfort","cute","friend","warm","tea","gentle","hug"]),
 ("teacup-bird","Teacup Bird & Ladybug","🐦",8,"1,2","animal","good-luck friends, springtime",["bird","ladybug","teacup","luck","spring","cute","friend","cosy","tea"]),
 ("teacup-deer","Teacup Fawn","🦌",8,"1,3","animal","gentleness, quiet wonder",["deer","fawn","penguin","teacup","gentle","sweet","cute","cosy","tea","wonder","calm"]),
 ("teacup-hamster","Teacup Hamster","🐹",8,"2,1","animal","small joys, homebody comfort",["hamster","guinea pig","teacup","cosy","cute","home","comfort","small","tea","sweet"]),
 ("teacup-shiba","Teacup Shiba","🐕",8,"2,2","animal","loyal, sunny companionship",["dog","shiba","puppy","teacup","loyal","cute","companion","cosy","tea","strawberry"]),
 ("teacup-hedgehog","Teacup Hedgehog","🦔",8,"2,3","animal","soft heart, prickly outside",["hedgehog","teacup","cosy","cute","soft","shy","comfort","tea","gentle"]),
 ("teacup-cat","Teacup Cat","🐈",8,"3,1","animal","independent comfort, lazy days",["cat","kitty","teacup","cosy","cute","independent","lazy","comfort","tea","home"]),
 ("teacup-fox","Teacup Fox","🦊",8,"3,2","animal","clever charm, cosy mischief",["fox","teacup","clever","cute","cosy","mischief","tea","sweet","autumn"]),
 ("teacup-panda","Teacup Panda","🐼",8,"3,3","animal","calm, cuddly, content",["panda","teacup","calm","cuddly","cute","cosy","content","tea","bamboo","gentle"]),
 # ---- Sheet 9 — Sweetheart Gallery ----
 ("sweetheart-apple","Sweetheart Apple","🍎",9,"1,1","love","the apple of my eye",["apple","heart","love","cherries","sweetheart","cute","romance","valentine","red","adore"]),
 ("winged-heart-star","Winged Heart Star","💫",9,"1,2","love","love that lifts you, wishes",["star","heart","wings","love","wish","fly","romance","dream","pink","magic","valentine"]),
 ("sprinkle-heart-donut","Heart Donut","🍩",9,"1,3","food","sweet treats, playful love",["donut","doughnut","heart","sprinkles","sweet","treat","love","dessert","playful","cute","bakery"]),
 ("pop-tart-heart","Heart Pastry","🧇",9,"2,1","food","comfort treats, mornings together",["pastry","poptart","heart","breakfast","sweet","comfort","treat","love","cosy","morning"]),
 ("valentine-latte","Valentine Latte","☕",9,"2,2","love","cosy dates, coffee love",["latte","coffee","cup","valentine","heart","love","date","cosy","drink","warm","sweet"]),
 ("sweet-tooth","Sweet Tooth","🦷",9,"2,3","love","sweet on you",["tooth","heart","sweet","love","quirky","playful","cute","red","humour"]),
 ("love-chips","Love Chips","🍟",9,"2,4","food","snack-time sweethearts",["chips","snack","heart","love","fun","playful","food","treat","cute","cosy"]),
 ("ladybug-heart","Ladybug Heart","🐞",9,"3,1","luck","lucky in love",["ladybug","heart","luck","love","red","spring","lucky","cute","romance","charm"]),
 ("love-cow","Love Cow","🐄",9,"3,2","animal","my moo-valentine",["cow","heart","love","farm","animal","cute","playful","valentine","country","sweet"]),
 ("love-monster","Love Monster","👾",9,"3,3","love","monster crush, big feelings",["monster","heart","love","blue","cute","playful","crush","quirky","fun","big feelings"]),
 ("penguin-heart","Penguin Heart","🐧",9,"3,4","love","penguins mate for life",["penguin","heart","love","devotion","loyal","partner","cute","winter","forever","romance"]),
]

# (id, name, blurb, style, fit_min, fit_max, vibe_tags)
BRACELETS = [
 ("bracelet-toggle-heart","Toggle Heart Bracelet","A classic double chain with a toggle clasp and a soft heart drop — endlessly charm-friendly.","classic",2,5,["classic","romantic","heart","everyday","charm","layering","timeless","love"]),
 ("bracelet-butterfly-charm","Butterfly Charm Bracelet","Layered chains scattered with butterflies — whimsical and made to be loaded with charms.","station",3,8,["butterfly","playful","whimsical","spring","layered","charm","fun","nature"]),
 ("bracelet-pearl-starburst","Pearl & Starburst Bracelet","Freshwater pearls meet a starburst — quietly elegant and a little celestial.","elegant",1,3,["pearl","star","elegant","romantic","bridal","celestial","classic","wedding"]),
 ("bracelet-dainty-tag","Dainty Tag Chain","The finest everyday chain with a tiny tag — barely there, goes with everything.","minimal",1,2,["dainty","minimal","simple","everyday","delicate","thin","subtle"]),
 ("bracelet-gold-bead","Gold Bead Bracelet","Warm matte gold beads — earthy, textural, beautiful on its own.","beaded",1,1,["bead","ball","warm","boho","earthy","textured","simple","minimal"]),
 ("bracelet-butterfly-chain","Butterfly Station Chain","A delicate chain with butterfly stations — light, feminine, springlike.","dainty",1,3,["butterfly","dainty","delicate","spring","thin","feminine","nature"]),
 ("bracelet-paperclip","Paperclip Chain","Cool elongated links — modern, a touch androgynous, very now.","modern",2,4,["paperclip","link","modern","cool","trendy","unisex","minimal"]),
 ("bracelet-triple-bead","Triple Sparkle Chain","A fine chain with three tiny sparkles — subtle shine for every day.","dainty",1,2,["sparkle","cz","dainty","delicate","subtle","thin","minimal"]),
 ("bracelet-disc-station","Disc Station Bracelet","Flat polished discs along a sleek chain — minimal and architectural.","modern",1,2,["disc","station","sleek","modern","minimal","geometric"]),
 ("bracelet-pearl-cross","Pearl & Cross Bracelet","Pearl, cross and coin — heirloom-feeling and full of meaning.","elegant",2,4,["pearl","cross","faith","elegant","meaningful","classic","charm","heirloom"]),
 ("bracelet-butterfly-bolo","Butterfly Bolo Bracelet","An adjustable bolo with a butterfly slider — one size, easy elegance.","adjustable",1,2,["butterfly","bolo","adjustable","dainty","delicate","minimal"]),
 ("bracelet-double-cuban","Double Cuban Chain","Two cuban chains layered together — bold but wearable, day to night.","bold",2,4,["cuban","figaro","bold","layered","statement","unisex","chunky"]),
 ("bracelet-chunky-cuban","Chunky Cuban Chain","A heavy curb chain that makes a statement on its own.","bold",1,2,["cuban","curb","chunky","bold","statement","confident","heavy","unisex"]),
 ("bracelet-daisy-station","Daisy Station Chain","Sweet daisies set along a chain — cheerful, springy, full of life.","station",3,8,["daisy","flower","cheerful","spring","floral","charm","playful","garden"]),
 ("bracelet-onyx-coin","Onyx Coin Paperclip","A paperclip chain anchored by a black onyx coin — edgy and modern.","modern",2,3,["onyx","black","coin","paperclip","edgy","modern","bold"]),
 ("bracelet-buckle-mesh","Buckle Mesh Bracelet","A sleek mesh band with a buckle motif — chic and unexpected.","sleek",1,1,["buckle","mesh","sleek","chic","fashion","modern","unique"]),
]


def js_str(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


def js_arr(items):
    return "[" + ",".join(js_str(t) for t in items) + "]"


def charm_block():
    out = io.StringIO()
    cur = None
    for cid, name, emoji, sheet, pos, cat, meaning, tags in CHARMS:
        if sheet != cur:
            cur = sheet
            out.write(f"\n    /* ---- Sheet {sheet} — {SHEET_LINES[sheet][1]} ---- */\n")
        out.write(
            f'    {{ id: {js_str(cid)}, name: {js_str(name)}, emoji: {js_str(emoji)}, sheet: {sheet}, pos: {js_str(pos)},\n'
            f'      category: {js_str(cat)}, meaning: {js_str(meaning)},\n'
            f'      tags: {js_arr(tags)} }},\n')
    return out.getvalue()


def sheets_block():
    out = io.StringIO()
    for s in sorted(SHEET_LINES):
        f, nm = SHEET_LINES[s]
        out.write(f'    {s}: {{ file: {js_str(f)}, name: {js_str(nm)} }},\n')
    return out.getvalue()


def bracelet_block():
    out = io.StringIO()
    out.write("  var BRACELETS = [\n")
    for bid, name, blurb, style, fmin, fmax, vibe in BRACELETS:
        out.write(
            f'    {{ id: {js_str(bid)}, name: {js_str(name)}, style: {js_str(style)},\n'
            f'      fit: [{fmin}, {fmax}], blurb: {js_str(blurb)},\n'
            f'      vibe: {js_arr(vibe)} }},\n')
    out.write("  ];\n")
    return out.getvalue()


def main():
    src = open("catalog.js").read()
    if "BRACELETS" in src:
        raise SystemExit("catalog.js already extended — aborting to avoid double insert.")

    # 1) add sheets 6-9: insert before the line that closes the SHEETS object.
    src = src.replace(
        '    5: { file: "charms/sheet-5-terracotta.jpeg", name: "Terracotta & Treasures" }\n  };',
        '    5: { file: "charms/sheet-5-terracotta.jpeg", name: "Terracotta & Treasures" },\n'
        + sheets_block().rstrip(",\n") + "\n  };")

    # 2) append new charms before the closing `];` of CHARMS.
    marker = "  ];\n\n  var API = { SHEETS: SHEETS, CHARMS: CHARMS };"
    assert marker in src, "CHARMS close marker not found"
    # ",\n" separates the appended charms from the last original entry (which
    # has no trailing comma before its `];`).
    src = src.replace(marker, ",\n" + charm_block() + "  ];\n\n" + bracelet_block() +
                      "\n  var API = { SHEETS: SHEETS, CHARMS: CHARMS, BRACELETS: BRACELETS };")

    # 3) expose bracelets on the global.
    src = src.replace(
        "    root.CHARM_CATALOG = CHARMS;\n    root.CHARM_SHEETS = SHEETS;",
        "    root.CHARM_CATALOG = CHARMS;\n    root.CHARM_SHEETS = SHEETS;\n    root.CHARM_BRACELETS = BRACELETS;")

    open("catalog.js", "w").write(src)
    print("catalog.js extended: +%d charms, +%d bracelets, +%d sheets" %
          (len(CHARMS), len(BRACELETS), len(SHEET_LINES)))


if __name__ == "__main__":
    main()

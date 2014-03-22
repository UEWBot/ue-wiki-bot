#! /usr/bin/python

"""
Script to insert image parameters to pages on UE Wiki
"""

import sys, os, operator
sys.path.append(os.environ['HOME'] + '/ue/ue_wikibots/pywikipedia')

import wikipedia, pagegenerators, catlib
import re, difflib

# Stuff for the wikipedia help system
parameterHelp = pagegenerators.parameterHelp + """\
"""

docuReplacements = {
    '&params;': parameterHelp
}

# Summary message when using this module as a stand-alone script
msg_standalone = {
    'en': u'Robot: Insert image parameters',
}

# Summary message  that will be appended to the normal message when
# cosmetic changes are made on the fly
msg_append = {
    'en': u'; insert image parameters',
}

imgRe = re.compile(ur'\|W*image\W*=\W*(?P<image>.*)')

params = [u'gear_1', u'gear_2', u'gear_3', u'gear_4']

class ImgBot:
    def __init__(self, generator, acceptall = False):
        self.generator = generator
        self.acceptall = acceptall
        # Load default summary message.
        wikipedia.setAction(wikipedia.translate(wikipedia.getSite(), msg_standalone))
        # Populate image_map
        self.image_map = {u'Concrete Block': u'item_concrete_block.png', u"Sin's Phoenix Rifle": u'item_sins_phoenix_rifle.png', u'357 Magnum': u'item_357_magnum.png', u'Painting Fragment 5 of 5': u'item_painting_fragment_5.PNG', u'Bullet Proof Vest': u'item_bullet_proof_vest.png', u'Steak Knife': u'item_steak_knife.png', u'Frag Grenade': u'item_frag_grenade.png', u'Casino Royale Gold Chip': u'item_casino_royale_gold_chip.png', u'G700': u'item_g700.png', u'Skull Fragment 3 of 5': u'item_skull_fragment_3.PNG', u'M241 Flamer': u'item_m241_flamer.png', u'Electric Knife': u'item_electric_knife.png', u'Nerve Gas Grenades': u'item_nerve_gas_grenades.png', u'Mystery Statue': u'gift_mystery_statue.png', u'El Machete': u'item_el_machete.png', u'Black Helm': u'item_black_helm.png', u'Shock Gloves': u'item_shock_gloves.png', u'Lucky Strike': u'item_lucky_strike.png', u'Condo': u'property_condo.png', u'Exotic': u'item_exotic.png', u'Platinum XXX Gloves': u'item_platinum_xxx_gloves.png', u'Fast Helmet': u'item_fast_helmet.png', u'Queen of Hearts': u'item_queen_of_hearts.png', u'Colosseum': u'property_colosseum.png', u'M-RS3 Turbo': u'item_sports_car.png', u'Stolen Diamond': u'item_stolen_diamond.png', u'The Tickler': u'item_the_tickler.png', u'Leviathan: Gun': u'item_leviathan_gun.png', u'Mossberg 590': u'item_mossberg_590.png', u'Red Dragon': u'item_red_dragon.png', u'Chainsaw': u'item_chainsaw.png', u'Tank: Chassis': u'item_tank_chassis.png', u'Hipster Shirt': u'item_hipster_shirt.png', u'Stunners': u'item_stunners.png', u'Leviathan: Torpedo': u'item_leviathan_torpedo.png', u'Apache: Fuel': u'item_apache_fuel.png', u'Casino Royale Red Chip': u'item_casino_royale_red_chip.png', u'Pimped Out SUV': u'item_pimped_out_suv.png', u'Street AK': u'item_street_ak.png', u'Pirate Keg': u'item_pirate_keg.png', u'Haymaker': u'item_haymaker.png', u'Revolver': u'item_revolver.PNG', u'Mystery Skull Watch': u'gift_mystery_skull_watch.png', u'Pirate Wheel': u'item_pirate_wheel.png', u'Red Present': u'item_red_present.png', u'Kastet 40mm Launcher': u'item_kastet_40mm_launcher.png', u'XLX Luxury Convertible': u'item_xlx_luxury_convertible.png', u'Glock 18': u'item_glock_18.png', u'DSR-1 Mafia Sniper': u'item_dsr_1_mafia_sniper.png', u'La Pistola': u'item_la_pistola.png', u'El Aguila (The Eagle)': u'item_el_aguila_the_eagle.png', u'Bullet Proof Suit': u'item_bullet_proof_suit.png', u"Reaper's Threshers": u'item_reapers_threshers.png', u'Blue Present': u'item_blue_present.png', u'El Enterrador': u'item_el_enterrador.png', u'Skull Fragment 1 of 5': u'item_skull_fragment_1.PNG', u'AWP Sniper': u'item_awp_sniper.png', u'Tank: Engine': u'item_tank_engine.png', u'Painting Fragment 2 of 5': u'item_painting_fragment_2.PNG', u'Dragon Core Handgun': u'item_dragon_core_handgun.png', u'Apache: Rotor': u'item_apache_rotor.png', u'Iron Hammer': u'item_iron_hammer.png', u'Razor Steel': u'item_razor_steel.png', u'G-10': u'item_g_10.png', u'Gold Present': u'item_gold_present.png', u'Casino Royale Green Chip': u'item_casino_royale_green_chip.png', u'Hurricane': u'item_hurricane.png', u'Ballistic Knife': u'item_ballistic_knife.png', u'AK101': u'item_ak101.png', u'Painting Fragment 4 of 5': u'item_painting_fragment_4.PNG', u'Thousand Year Old Blade': u'item_thousand_year_old_blade.png', u'Hegemony': u'item_hegemony.png', u'Candy Crusher Grenade': u'item_candy_crusher_grenade.png', u"SS 69: 'Thunder'": u'item_ss_69_thunder.png', u'SS 69: Transmission': u'item_ss_69_transmission.png', u'Personal Armory': u'property_personal armory.png', u'The Bonecrusher': u'item_the_bonecrusher.png', u'Ace of Hearts': u'item_ace_of_hearts.png', u'MP40': u'item_mp40.png', u'Sky Chaser': u'item_helicopter.png', u"Hunter's Trap": u'item_hunters_trap.png', u'Ball Buster': u'item_ball_buster.png', u"Enzo's Law": u'item_enzos_law.png', u'Ghost Armor': u'item_ghost_armor.png', u'Lucky Pocket Knife': u'item_lucky_pocket_knife.png', u'Leviathan: Navigation System': u'item_leviathan_navigation.png', u'Ski Mask': u'item_ski_mask.png', u'Apache: Tail': u'item_apache_tail.png', u'World War III': u'item_world_war_iii.png', u"Magnum 'Golden Eye'": u'item_magnum_golden_eye.png', u"Sara's Pumps (1/5)": u'item_saras_pumps.PNG', u'La Rosa': u'item_la_rosa.png', u'Diamond Fragment 1 of 5': u'item_diamond_fragment_1.png', u'Ballistic Mask': u'item_ballistic_mask.png', u'Big Bertha': u'item_big_bertha.png', u'CO2 Knife': u'item_co2_knife.png', u"Eve's Car": u'item_eves_car.png', u'Meck Titan': u'item_truck.png', u'Mafia Nutcracker': u'item_mafia_nutcracker.png', u'Money Stocking': u'item_money_stocking.png', u'Stolen Painting': u'item_stolen_painting.png', u"Boss Victor's Demolishers' Cell Phone": u'item_boss_victors_demolishers_cell_phone.png', u"Buster's Dog Tags": u'item_busters_dog_tags.png', u"Reaper's Phantom": u'item_reapers_phantom.png', u'Lightning': u'item_lightning.png', u'Armored Eurosedan': u'item_armored_eurosedan.png', u'Tank: Armor': u'item_tank_armor.png', u'Skull Ornament': u'item_skull_ornament.png', u'M21 EBR': u'item_m21_ebr.png', u'NBC Gas Mask': u'item_nbc_gas_mask.png', u'Shue Helmet': u'item_shue_helmet.png', u'Hunting Knife': u'item_hunting_knife.png', u'Gatling Gun': u'item_gatling_gun.png', u"Sara's Beauty (4/5)": u'item_saras_beauty.png', u'SwitchBlade': u'item_switchblade.png', u'Holo-Watch': u'item_holo_watch.png', u'Rhino': u'item_rhino.png', u'Gravity Knife': u'item_gravity_knife.png', u'Flowers for Sara (2/5)': u'item_flowers_for_sara.png', u'Kabar': u'item_kabar.png', u'Real Estate Agency': u'property_real_estate_agency.png', u'Gold Watch': u'item_gold_watch.png', u'Train Station': u'property_train_station.png', u"'Ice' Sniper Rifle": u'item_ice_sniper_rifle.png', u'Baby Eagle': u'item_baby_eagle.PNG', u'AK-12': u'item_ak_12.png', u'Skull Face 1 of 3': u'item_skull_face_1.PNG', u'Chain Wrapped Bat': u'item_chain_wrapped_bat.png', u'Dragon Core XM8': u'item_dragon_core_xm8.png', u'Blaze PDR': u'item_blaze_pdr.png', u'Ancient Statue': u'item_ancient_statue.png', u'5-0 Police Interceptor': u'item_5_0_police_interceptor.png', u'Illuminati Ring': u'item_illuminati_ring.png', u'Warmonger': u'item_warmonger.png', u'The Russian': u'item_the_russian.png', u'Butterfly Knife (Boss Reward)': u'item_butterfly_knife_boss_reward.png', u'Tactical Vest (Faction Reward)': u'item_tactical_vest_cartel.png', u'Reindeer Head': u'item_reindeer_head.png', u'Painting Fragment 3 of 5': u'item_painting_fragment_3.PNG', u'Vector SMG': u'item_vector_smg.png', u'Pirate Coin': u'item_pirate_coin.png', u'Aviators': u'item_aviators.png', u'Tank: Fuel': u'item_tank_fuel.png', u'MKIII Dragoon Rifle Gun': u'item_mkiii_dragoon_rifle_gun.png', u'Rusty Machete': u'item_rusty_machete.png', u'Lockpick Kit': u'item_lockpick_kit.png', u'Arms Factory': u'property_arms_factory.png', u'Bio Lab': u'property_bio_lab.png', u'The Grail': u'item_the_grail.png', u'Tank: Ammo': u'item_tank_ammo.png', u'Monster Hero Truck': u'item_monster_hero_truck.png', u'Lanzacohetes': u'item_lanzacohetes.png', u'Pistola de Oro': u'item_pistola_de_oro.png', u'Perfect Storm': u'item_perfect_storm.PNG', u'GT5': u'item_gt5.png', u'Cellphone Bomb': u'item_cellphone_bomb.png', u'Blade of Sorrow': u'item_blade_of_sorrow.png', u'Statue Fragment 5 of 5': u'item_statue_fragment_5.PNG', u'The Black Card': u'item_the_black_card.png', u'Bordeaux': u'item_bordeaux.png', u"Sara's Locket (5/5)": u'item_saras_locket.png', u"Boss Victor's Cell Phone": u'item_boss_victors_cell_phone.png', u'Statue Fragment 3 of 5': u'item_statue_fragment_3.PNG', u'Engraved Cane': u'item_engraved_cane.png', u'Skull Watch': u'item_skull_watch.png', u'Leather Gloves (Shop)': u'item_leather_gloves_shop.png', u'Golden Boy': u'item_golden_boy.png', u'Uncommon Recombinator': u'item_uncommon_recombinator.png', u'Bone Saw': u'item_bone_saw.png', u'Circular Saw': u'item_circular_saw.png', u'Predator': u'item_predator.png', u'Mystery Skull Medallion': u'gift_mystery_skull_medallion.png', u'Black Cleaver': u'item_black_cleaver.png', u'Skull Band 2 of 3': u'item_skull_band_2.PNG', u'VSS Rifle': u'item_vss_rifle.png', u'Skull Band 1 of 2': u'item_skull_band_1.PNG', u'Mega Casino': u'property_mega_casino.png', u'Vector LV2': u'item_vector_lv2.png', u'Sports Arena': u'property_sports_arena.png', u'Rare Recombinator': u'item_rare_recombinator.png', u'Armored SUV': u'item_armored_suv.png', u'Overwatch': u'item_overwatch.png', u"Boss Twins' Cell Phone": u'item_boss_twins_cell_phone.png', u'Stock Market Exchange': u'property_stock_market_exchange.png', u'AK-47': u'item_ak_47.png', u'Mansion': u'property_mansion.png', u"Rasputin's Skull": u'item_rasputins_skull.png', u'SS 69: Tire': u'item_ss_69_tire.png', u'Skull Symbol 2 of 2': u'item_skull_symbol_2.PNG', u'Mystery Skull Ring': u'gift_mystery_skull_ring.png', u'Fire Sword': u'item_fire_sword.png', u'Cattle Prod': u'item_cattle_prod.png', u'General Lee': u'item_general_lee.png', u'Glock': u'item_glock.png', u'Uzi SMG': u'item_uzi_smg.png', u'Omakase': u'item_omakase.png', u'The Business Man': u'item_the_business_man.png', u'Common Recombinator': u'item_common_recombinator.png', u'90Two': u'item_90two.png', u'Steel Beam': u'item_steel_beam.png', u'High Tech Panzer': u'item_high_tech_panzer.png', u'Pirate Bones': u'item_pirate_bones.png', u'Knights Templar Cell Phone': u'item_boss_knights_templars_cell_phone.png', u'Dojo': u'property_dojo.png', u"Buster's M76": u'item_busters_m76.png', u'Diamond Fragment 3 of 5': u'item_diamond_fragment_3.png', u'Ten of Hearts': u'item_ten_of_hearts.png', u'Mystery Diamond': u'gift_mystery_diamond.png', u'SS 69: Rims': u'item_ss_69_rims.png', u'Super Velociraptor': u'item_super_velociraptor.png', u'Stainless Revolver': u'item_stainless_revolver.png', u'Dragone': u'item_dragone.png', u'CNT Combat Armor': u'item_cnt_combat_armor.png', u'Secret Society Ring': u'item_secret_society_ring.png', u'Aladdin': u'item_aladdin.png', u'Paralyzing Pen': u'item_paralyzing_pen.png', u'LC9': u'item_lc9.png', u'Triple Shot Gun': u'item_triple_shot_gun.png', u'Bazooka': u'item_bazooka.png', u'Import Tuner': u'item_import_tuner.png', u'Apache: Gun': u'item_apache_gun.png', u'Dirty Harry': u'item_dirty_harry.png', u'Nightshade Blade': u'item_nightshade_blade.png', u'T-Rexxx': u'item_t_rexxx.png', u'Scorpion 500': u'item_scorpion_500.png', u'Skull Fragment 4 of 5': u'item_skull_fragment_4.PNG', u"Reaper's Guthook": u'item_reapers_guthook.png', u"Boss Frank's Cell Phone": u'item_boss_franks_cell_phone.png', u'Massacre Chainsaw': u'item_massacre_chainsaw.png', u'Auto9': u'item_auto9.png', u'Double Barrel Pistol': u'item_double_barrel_pistol.png', u'Iron Curtain': u'item_iron_curtain.png', u'Skull Fragment 2 of 5': u'item_skull_fragment_2.PNG', u'Old Bat': u'item_old_bat.png', u'Science Facility': u'property_science_facility.png', u'Caribbean Island': u'property_carribean_island.png', u'Divine Intervention': u'item_divine_intervention.png', u'Skorpion vz.61': u'item_skorpion_vz_61.png', u'Cadillac with Spinners': u'item_cadillac_with_spinners.png', u'CNT Stealth': u'item_cnt_stealth.png', u'Brixia Mortars': u'item_brixia_mortars.PNG', u'AW762 Sniper': u'item_aw762_sniper.png', u'API Bullets': u'item_api_bullets.png', u'Deadly Axe': u'item_deadly_axe.PNG', u'M1911': u'item_m1911.png', u'Nano-Thermite Bomb': u'item_nano_thermite_bomb.png', u'Leviathan: Plating': u'item_leviathan_plating.png', u'Tactical Knife': u'item_tactical_knife.png', u'Construction Company': u'property_construction_company.png', u'Roulette Rifle': u'item_roulette_rifle.png', u'Steel Factory': u'property_steel_factory.png', u'Home Run Bat (Boss Reward)': u'item_home_run_bat_boss.png', u'LV IV Body Armor': u'item_lv_iv_body_armor.png', u'Polarizers': u'item_polarizers.png', u'Skull Gear 3 of 3': u'item_skull_gear_3.PNG', u'Body Armor': u'item_body_armor.png', u'Timed Dynamite': u'item_timed_dynamite.png', u'Painting Fragment 1 of 5': u'item_painting_fragment_1.PNG', u'Dice': u'item_dice.png', u'FD Engine 187': u'item_fd_engine_187.png', u'Armor Piercing Rounds': u'item_armor_piercing_rounds.png', u'G19 Pistol': u'item_g19_pistol.png', u'Panda Hoodie': u'item_panda_hoodie.png', u'Hospital (Property)': u'property_hospital.png', u'MP-5': u'item_mp_5.png', u'Blue Camo M4': u'item_blue_camo_m4.png', u'Dragon Core Cell Phone': u'item_boss_dragon_cores_cell_phone.png', u"Reaper's Blaster Shotgun": u'item_reapers_blaster_shotgun.png', u'Diamond Fragment 4 of 5': u'item_diamond_fragment_4.png', u'Grappling Hook': u'item_grappling_hook.png', u'Machete': u'item_machete.png', u'SS 69: Body': u'item_ss_69_body.png', u'Defense Facility': u'property_defense_facility.png', u'DSR-1 Syndicate Sniper': u'item_dsr_1_syndicate_sniper.png', u'Thompson 2012': u'item_thompson_2012.png', u'Shotgun': u'item_shotgun.png', u'The Leviathan': u'item_the_leviathan.png', u'Casino Royale Blue Chip': u'item_casino_royale_blue_chip.png', u'Airport': u'property_airport.png', u'Las Vegas Strip': u'property_las_vegas_strip.png', u'Diamond Fragment 2 of 5': u'item_diamond_fragment_2.png', u'Tactical Vest (Shop)': u'item_tactical_vest_shop.png', u'Getaway Car': u'item_getaway_car.png', u'Red Eye': u'item_red_eye.png', u'Rail Gun': u'item_rail_gun.png', u'Nightshades Necklace': u'item_nightshades_necklace.png', u'Wakizashi': u'item_wakizashi.png', u'Boxing Gym': u'property_boxing_gym.png', u'War Factory': u'property_war_factory.png', u'Mystery Stolen Painting': u'gift_mystery_stolen_painting.png', u'Hairpin Knife': u'item_hairpin knife.png', u'Steyr TMP': u'item_steyr_tmp.png', u'Space Program': u'property_space_program.png', u"Mastermind's Rook": u'item_masterminds_rook.png', u'Kevlar Helmet': u'item_kevlar_helmet.png', u'LGI Mortar': u'item_lgi_mortar.png', u'Restaurant': u'property_restaurant.png', u'Volcano Sniper': u'item_volcano_sniper.png', u'Thumper': u'item_thumper.png', u'F1 Racecar': u'item_f1_racecar.png', u'Statue Fragment 4 of 5': u'item_statue_fragment_4.PNG', u'Shiny Crowbar': u'item_shiny_crowbar.png', u"Corrupt Cop's Cell Phone": u'item_corrupt_cops_cell_phone.png', u'MAC10 SMG': u'item_mac10_smg.PNG', u'Night Club': u'property_night club.png', u'Home Run Bat (Faction Reward)': u'item_home_run_bat_street.png', u"Captain's Rum": u'item_captains_rum.png', u'The Underdog': u'item_the_underdog.png', u'Statue Fragment 1 of 5': u'item_statue_fragment_1.PNG', u'Leviathan: Engine': u'item_leviathan_engine.png', u'Muramasa Reincarnation': u'item_muramasa_reincarnation.png', u'Bubba': u'item_bubba.png', u'Rainmaker': u'item_rainmaker.png', u'The Spectre': u'item_the_spectre.png', u'Stealth Armor': u'item_stealth_armor.png', u'Leather Gloves (Faction Reward)': u'item_leather_gloves_mafia.png', u"Sara's Jewelry (3/5)": u'item_saras_jewelry.png', u'King of Hearts': u'item_king_of_hearts.png', u'Schianova': u'item_schianova.png', u'SuperShottie': u'item_supershottie.png', u'Statue Fragment 2 of 5': u'item_statue_fragment_2.PNG', u"Boss Bone Breakers' Cell Phone": u'item_boss_bone_breakers_cell_phone.png', u'Wind Sword': u'item_wind_sword.png', u'Classic Muscle': u'item_classic_muscle.png', u"Reaper's AR-K Assault": u'item_reapers_ar_k_assault.png', u'Brass Knuckles': u'item_brass_knuckles.png', u'Master Cellphone': u'item_master_cellphone.png', u'Jade': u'item_jade.png', u'Riot Helmet': u'item_riot_helmet.png', u'Poison Fruitcake': u'item_poison_fruitcake.png', u'Earth Sword': u'item_earth_sword.png', u'2x4': u'item_2x4.png', u'Epic Recombinator': u'item_epic_recombinator.png', u'Sea Corsair': u'item_speed_boat.png', u'Plasma Cannon': u'item_plasma_cannon.png', u'ACP': u'item_acp.PNG', u'Financial Center': u'property_financial_center.png', u'Pirate Event Chest': u'item_pirate_event_chest.png', u'Pirate Hook': u'item_pirate_hook.png', u'Black Armor': u'item_black_armor.png', u'Baton': u'item_baton.png', u'Taser Baton': u'item_taser_baton.png', u"Street Rival's Cell Phone": u'item_street_rivals_cell_phone.png', u'Street Sweeper': u'item_street_sweeper.png', u'Skull Medallion': u'item_skull_medallion.png', u'The GodFather': u'item_the_godfather.png', u'Home-Made Tank': u'item_home_made_tank.png', u'Centurion Vest': u'item_centurion_vest.png', u'Penetrator': u'item_penetrator.png', u'Rusty Crowbar': u'item_rusty_crowbar.png', u'Eagle Eye': u'item_eagle_eye.png', u'Apache: Headset': u'item_apache_headset.png', u"Death Cartel's Cell Phone": u'item_boss_death_cartels_cell_phone.png', u'Ice Sword': u'item_ice_sword.png', u'Velociraptor': u'item_velociraptor.png', u'Nutcracker': u'item_nutcracker.png', u'Tie Breaker': u'item_tie_breaker.png', u'The Avenger': u'item_the_avenger.png', u'Ice': u'item_ice.png', u'Butterfly Knife (Faction Reward)': u'item_butterfly_knife_syndicate.png', u"Diablo's Demon": u'item_diablos_demon.png', u'Tire Iron': u'item_tire_iron.png', u'Master Chainsaw': u'item_master_chainsaw.png', u'Hover Drone': u'item_hover_drone.png', u'Famas H2': u'item_famas_h2.png', u'AK-47 Desert': u'item_ak_47_desert.PNG', u'Jack of Hearts': u'item_jack_of_hearts.png', u"Tony's Rocket": u'item_tonys_rocket.png', u'Retrofitted Apache': u'item_retrofitted_apache.png', u'Casino': u'property_casino.png', u'Street Baller': u'item_street_baller.png', u'Ace': u'item_ace.png', u'Green Present': u'item_green_present.png', u'Dragon Fang': u'item_dragon_fang.png', u'AR15 Sniper': u'item_ar15_sniper.png', u'Ultra Yacht': u'property_ultra_yacht.png', u'Gold Plated PPK': u'item_gold_plated_ppk.png', u"Seven's Bike": u'item_sevens_bike.png', u'Diamond Fragment 5 of 5': u'item_diamond_fragment_5.png', u'Skull Fragment 5 of 5': u'item_skull_fragment_5.PNG', u'Skull Ring': u'item_skull_ring.png', u'PAIN Knuckles': u'item_pain_knuckles.png', u'SS 69: Engine': u'item_ss_69_engine.png'}

        return
        self.image_map = {}
        # Loop through every item, property, and ingredient
        cats = [u'Items', u'Properties', u'Ingredients']
        for c in cats:
            cat = catlib.Category(wikipedia.getSite(), u'Category:%s' % c)
            for pg in cat.articles(recurse=True):
                key = pg.titleWithoutNamespace()
                if not key in self.image_map:
                    wikipedia.output("Looking up image for %s" % key)
                    # Retrieve the text of page 'key'
                    text = pg.get()

                    # Extract the image parameter
                    m = imgRe.search(text)
                    if m != None:
                        self.image_map[key] = m.group('image')
        wikipedia.output(self.image_map)

    def add_img_param(self, text, param, new_param=None):
        # TODO Don't add it if the image parameter is already there
        strRe = re.compile(ur'\|(?P<prefix>\W*%s\W*=\W*)(?P<value>[^\r]*)' % param)

        # If new_param not provided, use old_param plus "_img"
        if new_param == None:
            new_param = param + u'_img'

        for m in strRe.finditer(text):
            # Full string we matched
            old_param = ur'%s%s' % (m.group('prefix'), m.group('value'))
            wikipedia.output("Adding image for %s" % old_param)
            # New string to insert
            new_str = u'|%s=%s' % (new_param, self.image_map[m.group('value')])
            # Replace the old with old+new, just where we found the match
            # TODO Need to allow for the fact that these additions move other matches
            before = text[:m.start()] 
            after = text[m.end():]
            middle = re.sub(old_param, u'%s\n%s' % (old_param, new_str), text[m.start():m.end()])
            text = before + middle + after

        return text

    def treat(self, page):
        try:
            # Show the title of the page we're working on.
            # Highlight the title in purple.
            wikipedia.output(u"\n\n>>> \03{lightpurple}%s\03{default} <<<" % page.title())
            # TODO parameter to search for should be passed to the script
            text = page.get()
            old_text = text
            for param in params:
                text = self.add_img_param(text, param)
            # Give the user some context
            if old_text != text:
                wikipedia.output(text)
            wikipedia.showDiff(old_text, text)
            # TODO Modify to treat just whitespace as unchanged
            # Just comparing text with page.get() wasn't sufficient
            changes = False
            for diffline in difflib.ndiff(page.get().splitlines(), text.splitlines()):
                if not diffline.startswith(u'  '):
                    changes = True
                    break
            if changes:
                if not self.acceptall:
                    choice = wikipedia.inputChoice(u'Do you want to accept these changes?',  ['Yes', 'No', 'All'], ['y', 'N', 'a'], 'N')
                    if choice == 'a':
                        self.acceptall = True
                if self.acceptall or choice == 'y':
                    page.put(text)
            else:
                wikipedia.output('No changes were necessary in %s' % page.title())
        except wikipedia.NoPage:
            wikipedia.output("Page %s does not exist?!" % page.aslink())
        except wikipedia.IsRedirectPage:
            wikipedia.output("Page %s is a redirect; skipping." % page.aslink())
        except wikipedia.LockedPage:
            wikipedia.output("Page %s is locked?!" % page.aslink())

    def run(self):
        for page in self.generator:
            self.treat(page)

def main():
    #page generator
    gen = None
    pageTitle = []
    # This factory is responsible for processing command line arguments
    # that are also used by other scripts and that determine on which pages
    # to work on.
    genFactory = pagegenerators.GeneratorFactory()

    for arg in wikipedia.handleArgs():
        generator = genFactory.handleArg(arg)
        if generator:
            gen = generator
        else:
            pageTitle.append(arg)

    if pageTitle:
        page = wikipedia.Page(wikipedia.getSite(), ' '.join(pageTitle))
        gen = iter([page])
    if not gen:
        wikipedia.showHelp()
    else:
        preloadingGen = pagegenerators.PreloadingGenerator(gen)
        bot = ImgBot(preloadingGen)
        bot.run()

if __name__ == "__main__":
    try:
        main()
    finally:
        wikipedia.stopme()


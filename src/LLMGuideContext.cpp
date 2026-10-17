#include "LLMGuideContext.h"
#include "DBCStores.h"
#include "Item.h"
#include "ObjectMgr.h"
#include "Player.h"
#include "ReputationMgr.h"
#include <boost/bind/placeholders.hpp>

// Older Boost JSON parsers assume global bind placeholders, which the core
// disables. Expose only the required placeholder inside the parser namespace.
namespace boost::property_tree::json_parser::detail
{
using boost::placeholders::_1;
}

#include <boost/property_tree/json_parser.hpp>
#include <boost/property_tree/ptree.hpp>
#include <sstream>
#include <ctime>

char const* GetGuideEquipmentSlotName(uint8 slot)
{
    switch (slot)
    {
        case EQUIPMENT_SLOT_HEAD: return "Head";
        case EQUIPMENT_SLOT_NECK: return "Neck";
        case EQUIPMENT_SLOT_SHOULDERS: return "Shoulders";
        case EQUIPMENT_SLOT_BODY: return "Shirt";
        case EQUIPMENT_SLOT_CHEST: return "Chest";
        case EQUIPMENT_SLOT_WAIST: return "Waist";
        case EQUIPMENT_SLOT_LEGS: return "Legs";
        case EQUIPMENT_SLOT_FEET: return "Feet";
        case EQUIPMENT_SLOT_WRISTS: return "Wrists";
        case EQUIPMENT_SLOT_HANDS: return "Hands";
        case EQUIPMENT_SLOT_FINGER1: return "Ring 1";
        case EQUIPMENT_SLOT_FINGER2: return "Ring 2";
        case EQUIPMENT_SLOT_TRINKET1: return "Trinket 1";
        case EQUIPMENT_SLOT_TRINKET2: return "Trinket 2";
        case EQUIPMENT_SLOT_BACK: return "Back";
        case EQUIPMENT_SLOT_MAINHAND: return "Main hand";
        case EQUIPMENT_SLOT_OFFHAND: return "Off hand";
        case EQUIPMENT_SLOT_RANGED: return "Ranged";
        case EQUIPMENT_SLOT_TABARD: return "Tabard";
        default: return "Unknown slot";
    }
}

std::string BuildGuideSnapshot(Player* player, std::string const& summary)
{
    // Property tree serializes scalar values as strings. The bridge decodes
    // each typed field explicitly; empty collections are represented by "".
    using boost::property_tree::ptree;
    ptree snapshot;
    snapshot.put("version", 1);
    snapshot.put("summary", summary);
    snapshot.put("level", uint32(player->GetLevel()));
    snapshot.put("race_mask", player->getRaceMask());
    snapshot.put("class_mask", player->getClassMask());
    snapshot.put("captured_at", time(nullptr));

    ptree skills;
    for (uint32 id = 1; id < sSkillLineStore.GetNumRows(); ++id)
        if (player->GetSkillValue(id))
            skills.put(std::to_string(id), player->GetSkillValue(id));
    snapshot.add_child("skills", skills);

    ptree reputation;
    for (auto const& [id, state] : player->GetReputationMgr().GetStateList())
        reputation.put(std::to_string(state.ID),
            player->GetReputationMgr().GetReputation(state.ID));
    snapshot.add_child("reputation", reputation);

    ptree quests;
    // Cheap filters avoid expensive condition checks for unrelated classes,
    // races and levels. CanTakeQuest remains the authority on eligibility.
    for (auto const& [id, quest] : sObjectMgr->GetQuestTemplates())
    {
        if (!player->SatisfyQuestLevel(quest, false) ||
            !player->SatisfyQuestClass(quest, false) ||
            !player->SatisfyQuestRace(quest, false))
            continue;
        if (player->CanTakeQuest(quest, false))
        {
            ptree value;
            value.put_value(id);
            quests.push_back({"", value});
        }
    }
    snapshot.add_child("eligible_quest_ids", quests);

    ptree equipment;
    for (uint8 slot = EQUIPMENT_SLOT_START; slot < EQUIPMENT_SLOT_END; ++slot)
        if (Item* item = player->GetItemByPos(INVENTORY_SLOT_BAG_0, slot))
            equipment.put(std::to_string(slot), item->GetEntry());
    snapshot.add_child("equipment", equipment);

    ptree spells;
    for (auto const& [id, spell] : player->GetSpellMap())
        if (spell && spell->State != PLAYERSPELL_REMOVED)
        {
            ptree value;
            value.put_value(id);
            spells.push_back({"", value});
        }
    snapshot.add_child("known_spells", spells);

    std::ostringstream output;
    boost::property_tree::write_json(output, snapshot, false);
    return output.str();
}

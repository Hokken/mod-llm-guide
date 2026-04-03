/*
 * Copyright (C) 2024+ AzerothCore <www.azerothcore.org>
 * Released under GNU AGPL v3 license: https://github.com/azerothcore/azerothcore-wotlk/blob/master/LICENSE-AGPL3
 */

#include "LLMGuideConfig.h"
#include "Chat.h"
#include "Config.h"
#include "DatabaseEnv.h"
#include "DBCStores.h"
#include "Group.h"
#include "Guild.h"
#include "GuildMgr.h"
#include "Log.h"
#include "MapMgr.h"
#include "ObjectMgr.h"
#include "Opcodes.h"
#include "Player.h"
#include "PlayerScript.h"
#include "ScriptMgr.h"
#include "World.h"
#include "WorldPacket.h"
#include "WorldSession.h"
#include <algorithm>
#include <cctype>
#include <fstream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <unordered_map>

// The name players whisper to for the AI assistant
static const std::string GUIDE_NAME = "AzerothGuide";
static const std::string GUIDE_NAME_LOWER = "azerothguide";

using namespace Acore::ChatCommands;

// Track cooldowns per player
static std::unordered_map<uint32, time_t> playerCooldowns;

// Store player equipment for item link matching (guid -> map of item name -> item ID)
static std::unordered_map<uint32, std::unordered_map<std::string, uint32>> playerEquipment;

static constexpr uint32 DEFAULT_HISTORY_COUNT = 5;
static constexpr uint32 MAX_HISTORY_COUNT = 10;

// Forward declaration
static bool SubmitQuestion(Player* player, const std::string& question, bool isWhisper = false);

// Helper function to get class name
static const char* GetClassName(uint8 classId)
{
    switch (classId)
    {
        case CLASS_WARRIOR:     return "Warrior";
        case CLASS_PALADIN:     return "Paladin";
        case CLASS_HUNTER:      return "Hunter";
        case CLASS_ROGUE:       return "Rogue";
        case CLASS_PRIEST:      return "Priest";
        case CLASS_DEATH_KNIGHT: return "Death Knight";
        case CLASS_SHAMAN:      return "Shaman";
        case CLASS_MAGE:        return "Mage";
        case CLASS_WARLOCK:     return "Warlock";
        case CLASS_DRUID:       return "Druid";
        default:                return "Unknown";
    }
}

// Helper function to get race name
static const char* GetRaceName(uint8 raceId)
{
    switch (raceId)
    {
        case RACE_HUMAN:        return "Human";
        case RACE_ORC:          return "Orc";
        case RACE_DWARF:        return "Dwarf";
        case RACE_NIGHTELF:     return "Night Elf";
        case RACE_UNDEAD_PLAYER: return "Undead";
        case RACE_TAUREN:       return "Tauren";
        case RACE_GNOME:        return "Gnome";
        case RACE_TROLL:        return "Troll";
        case RACE_BLOODELF:     return "Blood Elf";
        case RACE_DRAENEI:      return "Draenei";
        default:                return "Unknown";
    }
}

// Helper function to get faction
static const char* GetFaction(uint8 raceId)
{
    switch (raceId)
    {
        case RACE_HUMAN:
        case RACE_DWARF:
        case RACE_NIGHTELF:
        case RACE_GNOME:
        case RACE_DRAENEI:
            return "Alliance";
        case RACE_ORC:
        case RACE_UNDEAD_PLAYER:
        case RACE_TAUREN:
        case RACE_TROLL:
        case RACE_BLOODELF:
            return "Horde";
        default:
            return "Unknown";
    }
}

// Helper function to get talent tree name for a class
// Tree indices: 0, 1, 2 for the three specs
static const char* GetTalentTreeName(uint8 classId, uint8 treeIndex)
{
    // WotLK talent tree names per class (tree 0, 1, 2)
    switch (classId)
    {
        case CLASS_WARRIOR:
            switch (treeIndex) {
                case 0: return "Arms";
                case 1: return "Fury";
                case 2: return "Protection";
            }
            break;
        case CLASS_PALADIN:
            switch (treeIndex) {
                case 0: return "Holy";
                case 1: return "Protection";
                case 2: return "Retribution";
            }
            break;
        case CLASS_HUNTER:
            switch (treeIndex) {
                case 0: return "Beast Mastery";
                case 1: return "Marksmanship";
                case 2: return "Survival";
            }
            break;
        case CLASS_ROGUE:
            switch (treeIndex) {
                case 0: return "Assassination";
                case 1: return "Combat";
                case 2: return "Subtlety";
            }
            break;
        case CLASS_PRIEST:
            switch (treeIndex) {
                case 0: return "Discipline";
                case 1: return "Holy";
                case 2: return "Shadow";
            }
            break;
        case CLASS_DEATH_KNIGHT:
            switch (treeIndex) {
                case 0: return "Blood";
                case 1: return "Frost";
                case 2: return "Unholy";
            }
            break;
        case CLASS_SHAMAN:
            switch (treeIndex) {
                case 0: return "Elemental";
                case 1: return "Enhancement";
                case 2: return "Restoration";
            }
            break;
        case CLASS_MAGE:
            switch (treeIndex) {
                case 0: return "Arcane";
                case 1: return "Fire";
                case 2: return "Frost";
            }
            break;
        case CLASS_WARLOCK:
            switch (treeIndex) {
                case 0: return "Affliction";
                case 1: return "Demonology";
                case 2: return "Destruction";
            }
            break;
        case CLASS_DRUID:
            switch (treeIndex) {
                case 0: return "Balance";
                case 1: return "Feral";
                case 2: return "Restoration";
            }
            break;
    }
    return "Unknown";
}

// Build talent spec string like "Beast Mastery (31/5/5)"
static std::string GetTalentSpec(Player* player)
{
    uint8 specPoints[3] = {0, 0, 0};
    player->GetTalentTreePoints(specPoints);

    uint8 totalPoints = specPoints[0] + specPoints[1] + specPoints[2];
    if (totalPoints == 0)
        return "No talents";

    // Find primary tree (most points)
    uint8 primaryTree = 0;
    if (specPoints[1] > specPoints[primaryTree]) primaryTree = 1;
    if (specPoints[2] > specPoints[primaryTree]) primaryTree = 2;

    std::ostringstream ss;
    ss << GetTalentTreeName(player->getClass(), primaryTree)
       << " (" << (int)specPoints[0] << "/" << (int)specPoints[1] << "/" << (int)specPoints[2] << ")";

    return ss.str();
}

// Helper to get short stat name
static const char* GetStatShortName(uint32 statType)
{
    switch (statType)
    {
        case ITEM_MOD_AGILITY:              return "Agi";
        case ITEM_MOD_STRENGTH:             return "Str";
        case ITEM_MOD_INTELLECT:            return "Int";
        case ITEM_MOD_SPIRIT:               return "Spi";
        case ITEM_MOD_STAMINA:              return "Sta";
        case ITEM_MOD_HIT_RATING:           return "Hit";
        case ITEM_MOD_CRIT_RATING:          return "Crit";
        case ITEM_MOD_HASTE_RATING:         return "Haste";
        case ITEM_MOD_ATTACK_POWER:         return "AP";
        case ITEM_MOD_RANGED_ATTACK_POWER:  return "RAP";
        case ITEM_MOD_SPELL_POWER:          return "SP";
        case ITEM_MOD_DEFENSE_SKILL_RATING: return "Def";
        case ITEM_MOD_DODGE_RATING:         return "Dodge";
        case ITEM_MOD_PARRY_RATING:         return "Parry";
        case ITEM_MOD_BLOCK_RATING:         return "Block";
        case ITEM_MOD_EXPERTISE_RATING:     return "Exp";
        case ITEM_MOD_ARMOR_PENETRATION_RATING: return "ArP";
        case ITEM_MOD_MANA_REGENERATION:    return "MP5";
        case ITEM_MOD_RESILIENCE_RATING:    return "Resil";
        default:                            return nullptr;
    }
}

// Build detailed equipment list with item names and stats
// Also populates playerEquipment map for item name -> ID lookups
static std::string GetEquipmentDetails(Player* player)
{
    std::ostringstream ss;
    std::vector<std::string> items;
    uint32 guid = player->GetGUID().GetCounter();

    // Clear and rebuild equipment map for this player
    playerEquipment[guid].clear();

    // Key equipment slots (skip shirt/tabard)
    uint8 slots[] = {
        EQUIPMENT_SLOT_HEAD, EQUIPMENT_SLOT_NECK, EQUIPMENT_SLOT_SHOULDERS,
        EQUIPMENT_SLOT_CHEST, EQUIPMENT_SLOT_WAIST, EQUIPMENT_SLOT_LEGS,
        EQUIPMENT_SLOT_FEET, EQUIPMENT_SLOT_WRISTS, EQUIPMENT_SLOT_HANDS,
        EQUIPMENT_SLOT_FINGER1, EQUIPMENT_SLOT_FINGER2,
        EQUIPMENT_SLOT_TRINKET1, EQUIPMENT_SLOT_TRINKET2,
        EQUIPMENT_SLOT_BACK, EQUIPMENT_SLOT_MAINHAND, EQUIPMENT_SLOT_OFFHAND,
        EQUIPMENT_SLOT_RANGED
    };

    for (uint8 slot : slots)
    {
        Item* item = player->GetItemByPos(INVENTORY_SLOT_BAG_0, slot);
        if (!item)
            continue;

        ItemTemplate const* proto = item->GetTemplate();
        if (!proto)
            continue;

        // Store item name -> ID for link matching
        playerEquipment[guid][proto->Name1] = proto->ItemId;

        std::ostringstream itemStr;
        itemStr << "[" << proto->Name1 << "]";

        // Add item level
        itemStr << " (iLvl " << proto->ItemLevel;

        // Add key stats
        std::vector<std::string> statList;
        for (uint32 i = 0; i < proto->StatsCount && i < MAX_ITEM_PROTO_STATS; ++i)
        {
            const char* statName = GetStatShortName(proto->ItemStat[i].ItemStatType);
            if (statName && proto->ItemStat[i].ItemStatValue != 0)
            {
                statList.push_back((proto->ItemStat[i].ItemStatValue > 0 ? "+" : "") +
                    std::to_string(proto->ItemStat[i].ItemStatValue) + " " + statName);
            }
        }

        // Add armor for armor pieces
        if (proto->Armor > 0 && proto->Class == ITEM_CLASS_ARMOR)
        {
            statList.push_back(std::to_string(proto->Armor) + " Armor");
        }

        if (!statList.empty())
        {
            itemStr << ", ";
            for (size_t i = 0; i < statList.size() && i < 3; ++i)  // Limit to 3 stats
            {
                if (i > 0) itemStr << "/";
                itemStr << statList[i];
            }
        }

        itemStr << ")";
        items.push_back(itemStr.str());
    }

    if (items.empty())
        return "";

    ss << "Equipment: ";
    for (size_t i = 0; i < items.size(); ++i)
    {
        if (i > 0) ss << ", ";
        ss << items[i];
    }

    return ss.str();
}

// Helper function to format gold
static std::string FormatGold(uint32 copper)
{
    uint32 gold = copper / 10000;
    uint32 silver = (copper % 10000) / 100;
    uint32 copperRem = copper % 100;

    std::ostringstream ss;
    if (gold > 0)
        ss << gold << "g ";
    if (silver > 0 || gold > 0)
        ss << silver << "s ";
    ss << copperRem << "c";
    return ss.str();
}

// Helper function to get item quality color
static const char* GetQualityColor(uint8 quality)
{
    switch (quality)
    {
        case 0: return "9d9d9d";  // Poor (gray)
        case 1: return "ffffff";  // Common (white)
        case 2: return "1eff00";  // Uncommon (green)
        case 3: return "0070dd";  // Rare (blue)
        case 4: return "a335ee";  // Epic (purple)
        case 5: return "ff8000";  // Legendary (orange)
        case 6: return "e6cc80";  // Artifact (light gold)
        case 7: return "00ccff";  // Heirloom (light blue)
        default: return "ffffff";
    }
}

// Convert [[item:ID:Name:Quality]] markers to WoW item links
static std::string ConvertItemLinks(const std::string& text)
{
    std::string result = text;
    size_t pos = 0;

    // Pattern: [[item:ID:Name:Quality]]
    while ((pos = result.find("[[item:", pos)) != std::string::npos)
    {
        size_t endPos = result.find("]]", pos);
        if (endPos == std::string::npos)
            break;

        // Extract the content between [[item: and ]]
        std::string content = result.substr(pos + 7, endPos - pos - 7);

        // Parse ID:Name or ID:Name:Quality
        size_t firstColon = content.find(':');
        if (firstColon == std::string::npos)
        {
            pos = endPos + 2;
            continue;
        }

        size_t lastColon = content.rfind(':');
        std::string idStr = content.substr(0, firstColon);
        std::string name;
        uint8 quality = 2;  // Default to green (uncommon)

        if (firstColon != lastColon)
        {
            // Format: ID:Name:Quality
            name = content.substr(firstColon + 1, lastColon - firstColon - 1);
            std::string qualityStr = content.substr(lastColon + 1);
            try { quality = static_cast<uint8>(std::stoul(qualityStr)); } catch (...) {}
        }
        else
        {
            // Format: ID:Name (no quality, default to green)
            name = content.substr(firstColon + 1);
        }

        try
        {
            uint32 itemId = std::stoul(idStr);

            // Build WoW item link
            // Format: |cffCOLOR|Hitem:ID:0:0:0:0:0:0:0:0|h[Name]|h|r
            std::ostringstream link;
            link << "|cff" << GetQualityColor(quality)
                 << "|Hitem:" << itemId << ":0:0:0:0:0:0:0:0|h[" << name << "]|h|r";

            // Replace the marker with the link
            result.replace(pos, endPos - pos + 2, link.str());

            // Continue searching after the replacement
            pos += link.str().length();
        }
        catch (...)
        {
            // If parsing fails, skip this marker
            pos = endPos + 2;
        }
    }

    return result;
}

// Convert [[spell:ID:Name]] markers to WoW spell links
static std::string ConvertSpellLinks(const std::string& text)
{
    std::string result = text;
    size_t pos = 0;

    // Pattern: [[spell:ID:Name]]
    while ((pos = result.find("[[spell:", pos)) != std::string::npos)
    {
        size_t endPos = result.find("]]", pos);
        if (endPos == std::string::npos)
            break;

        // Extract the content between [[spell: and ]]
        std::string content = result.substr(pos + 8, endPos - pos - 8);

        // Parse ID:Name
        size_t colonPos = content.find(':');

        if (colonPos != std::string::npos)
        {
            std::string idStr = content.substr(0, colonPos);
            std::string name = content.substr(colonPos + 1);

            try
            {
                uint32 spellId = std::stoul(idStr);

                // Build WoW spell link (spell links are light blue: 71d5ff)
                // Format: |cff71d5ff|Hspell:ID|h[Name]|h|r
                std::ostringstream link;
                link << "|cff71d5ff|Hspell:" << spellId << "|h[" << name << "]|h|r";

                result.replace(pos, endPos - pos + 2, link.str());
                pos += link.str().length();
            }
            catch (...)
            {
                pos = endPos + 2;
            }
        }
        else
        {
            pos = endPos + 2;
        }
    }

    return result;
}

// Convert [[quest:ID:Name:Level]] or [[quest:ID:Name]] markers to WoW quest links
static std::string ConvertQuestLinks(const std::string& text)
{
    std::string result = text;
    size_t pos = 0;

    // Pattern: [[quest:ID:Name:Level]] or [[quest:ID:Name]]
    while ((pos = result.find("[[quest:", pos)) != std::string::npos)
    {
        size_t endPos = result.find("]]", pos);
        if (endPos == std::string::npos)
            break;

        // Extract the content between [[quest: and ]]
        std::string content = result.substr(pos + 8, endPos - pos - 8);

        // Parse ID:Name or ID:Name:Level
        size_t firstColon = content.find(':');
        if (firstColon == std::string::npos)
        {
            pos = endPos + 2;
            continue;
        }

        size_t lastColon = content.rfind(':');
        std::string idStr = content.substr(0, firstColon);
        std::string name;
        uint32 level = 0;  // Default level

        if (firstColon != lastColon)
        {
            // Format: ID:Name:Level (3 parts)
            name = content.substr(firstColon + 1, lastColon - firstColon - 1);
            std::string levelStr = content.substr(lastColon + 1);
            try { level = std::stoul(levelStr); } catch (...) {}
        }
        else
        {
            // Format: ID:Name (2 parts, no level)
            name = content.substr(firstColon + 1);
        }

        try
        {
            uint32 questId = std::stoul(idStr);

            // Build WoW quest link (quest links are yellow: ffff00)
            // Format: |cffFFFF00|Hquest:ID:Level|h[Name]|h|r
            std::ostringstream link;
            link << "|cffffff00|Hquest:" << questId << ":" << level << "|h[" << name << "]|h|r";

            result.replace(pos, endPos - pos + 2, link.str());
            pos += link.str().length();
        }
        catch (...)
        {
            pos = endPos + 2;
        }
    }

    return result;
}

// Convert [[npc:ID:Name]] markers to highlighted NPC text
// NPCs are displayed in green (common NPC color)
static std::string ConvertNpcLinks(const std::string& text)
{
    std::string result = text;
    size_t pos = 0;

    // Pattern: [[npc:ID:Name]]
    while ((pos = result.find("[[npc:", pos)) != std::string::npos)
    {
        size_t endPos = result.find("]]", pos);
        if (endPos == std::string::npos)
            break;

        // Extract the content between [[npc: and ]]
        std::string content = result.substr(pos + 6, endPos - pos - 6);

        // Parse ID:Name
        size_t colonPos = content.find(':');

        if (colonPos != std::string::npos)
        {
            std::string name = content.substr(colonPos + 1);

            // NPCs get a green color (like friendly NPCs in WoW)
            std::string coloredName = "|cff00ff00" + name + "|r";

            result.replace(pos, endPos - pos + 2, coloredName);
            pos += coloredName.length();
        }
        else
        {
            pos = endPos + 2;
        }
    }

    return result;
}

// Convert [Item Name] mentions to [[item:ID:Name]] if item is in player's equipment
static std::string ConvertEquipmentMentions(const std::string& text, uint32 playerGuid)
{
    auto it = playerEquipment.find(playerGuid);
    if (it == playerEquipment.end() || it->second.empty())
        return text;

    std::string result = text;
    const auto& equipMap = it->second;

    // Look for [Item Name] patterns that aren't already [[item:...]] markers
    size_t pos = 0;
    while ((pos = result.find('[', pos)) != std::string::npos)
    {
        // Skip if it's already a marker [[
        if (pos + 1 < result.length() && result[pos + 1] == '[')
        {
            pos += 2;
            continue;
        }

        // Skip if it's part of a WoW link |h[
        if (pos >= 2 && result[pos - 1] == 'h' && result[pos - 2] == '|')
        {
            pos++;
            continue;
        }

        size_t endPos = result.find(']', pos);
        if (endPos == std::string::npos)
            break;

        // Extract the item name
        std::string itemName = result.substr(pos + 1, endPos - pos - 1);

        // Check if this item is in the player's equipment
        auto equipIt = equipMap.find(itemName);
        if (equipIt != equipMap.end())
        {
            // Replace [Item Name] with [[item:ID:Name]]
            std::ostringstream marker;
            marker << "[[item:" << equipIt->second << ":" << itemName << "]]";
            result.replace(pos, endPos - pos + 1, marker.str());
            pos += marker.str().length();
        }
        else
        {
            pos = endPos + 1;
        }
    }

    return result;
}

// Convert all link markers to WoW hyperlinks
static std::string ConvertAllLinks(const std::string& text, uint32 playerGuid = 0)
{
    std::string result = text;
    // First convert equipment mentions to [[item:...]] markers
    if (playerGuid > 0)
        result = ConvertEquipmentMentions(result, playerGuid);
    result = ConvertItemLinks(result);
    result = ConvertSpellLinks(result);
    result = ConvertQuestLinks(result);
    result = ConvertNpcLinks(result);
    return result;
}

// Strip markdown formatting from text (bold, italic, etc.)
// Removes **, *, ***, __, _, ___ wrappers around text
static std::string StripMarkdown(const std::string& text)
{
    std::string result = text;

    // Remove *** (bold+italic) - must be done before ** and *
    size_t pos = 0;
    while ((pos = result.find("***", pos)) != std::string::npos)
    {
        size_t endPos = result.find("***", pos + 3);
        if (endPos != std::string::npos)
        {
            // Remove closing ***
            result.erase(endPos, 3);
            // Remove opening ***
            result.erase(pos, 3);
            // Don't advance pos, check from same position
        }
        else
        {
            pos += 3;
        }
    }

    // Remove ** (bold)
    pos = 0;
    while ((pos = result.find("**", pos)) != std::string::npos)
    {
        size_t endPos = result.find("**", pos + 2);
        if (endPos != std::string::npos)
        {
            result.erase(endPos, 2);
            result.erase(pos, 2);
        }
        else
        {
            pos += 2;
        }
    }

    // Remove * (italic) - but avoid breaking [[item:...]] markers
    pos = 0;
    while ((pos = result.find('*', pos)) != std::string::npos)
    {
        // Skip if it's part of a marker [[...]]
        if (pos > 0 && result[pos - 1] == '[')
        {
            pos++;
            continue;
        }
        size_t endPos = result.find('*', pos + 1);
        if (endPos != std::string::npos && endPos - pos < 100)  // Reasonable max length
        {
            result.erase(endPos, 1);
            result.erase(pos, 1);
        }
        else
        {
            pos++;
        }
    }

    // Remove ___ (bold+italic underscores)
    pos = 0;
    while ((pos = result.find("___", pos)) != std::string::npos)
    {
        size_t endPos = result.find("___", pos + 3);
        if (endPos != std::string::npos)
        {
            result.erase(endPos, 3);
            result.erase(pos, 3);
        }
        else
        {
            pos += 3;
        }
    }

    // Remove __ (bold underscores)
    pos = 0;
    while ((pos = result.find("__", pos)) != std::string::npos)
    {
        size_t endPos = result.find("__", pos + 2);
        if (endPos != std::string::npos)
        {
            result.erase(endPos, 2);
            result.erase(pos, 2);
        }
        else
        {
            pos += 2;
        }
    }

    return result;
}

static std::string CollapseWhitespace(const std::string& text)
{
    std::string result;
    result.reserve(text.length());

    bool previousWasSpace = false;
    for (char ch : text)
    {
        if (ch == '\r' || ch == '\n' || ch == '\t')
            ch = ' ';

        if (ch == ' ')
        {
            if (!previousWasSpace)
                result.push_back(ch);

            previousWasSpace = true;
            continue;
        }

        result.push_back(ch);
        previousWasSpace = false;
    }

    if (!result.empty() && result.front() == ' ')
        result.erase(result.begin());

    while (!result.empty() && result.back() == ' ')
        result.pop_back();

    return result;
}

static std::string TruncateText(const std::string& text, size_t maxLength)
{
    if (text.length() <= maxLength)
        return text;

    if (maxLength <= 3)
        return text.substr(0, maxLength);

    return text.substr(0, maxLength - 3) + "...";
}

static std::string NormalizeGuideText(const std::string& text)
{
    std::string cleaned = StripMarkdown(text);
    return CollapseWhitespace(cleaned);
}

static std::string ConvertGuideLinks(
    Player* player,
    const std::string& normalizedText)
{
    uint32 guid = player ? player->GetGUID().GetCounter() : 0;
    return ConvertAllLinks(normalizedText, guid);
}

static std::string ProcessGuideText(Player* player, const std::string& text)
{
    return ConvertGuideLinks(player, NormalizeGuideText(text));
}

static bool SplitCommandTail(
    const std::string& input,
    const std::string& prefix,
    std::string& tail)
{
    if (input.rfind(prefix, 0) != 0)
        return false;

    tail = input.substr(prefix.length());
    return true;
}

static bool TryParsePositiveUInt32(
    const std::string& text,
    uint32& value)
{
    bool isDigitsOnly = !text.empty() && std::all_of(
        text.begin(),
        text.end(),
        [](unsigned char ch) { return std::isdigit(ch) != 0; });

    if (!isDigitsOnly)
        return false;

    try
    {
        unsigned long parsed = std::stoul(text);
        if (parsed == 0 ||
            parsed > std::numeric_limits<uint32>::max())
        {
            return false;
        }

        value = static_cast<uint32>(parsed);
        return true;
    }
    catch (const std::exception&)
    {
        return false;
    }
}

static bool TryParseHistoryArguments(
    const std::string& input,
    uint32& requestedCount,
    uint32& requestedPage)
{
    requestedCount = DEFAULT_HISTORY_COUNT;
    requestedPage = 1;

    if (input == "history")
        return true;

    std::string tail;
    if (!SplitCommandTail(input, "history ", tail))
        return false;

    size_t pageMarker = tail.find(" page ");
    if (pageMarker != std::string::npos)
    {
        std::string countStr = tail.substr(0, pageMarker);
        std::string pageStr = tail.substr(pageMarker + 6);

        if (!TryParsePositiveUInt32(countStr, requestedCount) ||
            !TryParsePositiveUInt32(pageStr, requestedPage))
        {
            return false;
        }

        return true;
    }

    if (tail.rfind("page ", 0) == 0)
    {
        std::string pageStr = tail.substr(5);
        return TryParsePositiveUInt32(pageStr, requestedPage);
    }

    return TryParsePositiveUInt32(tail, requestedCount);
}

static std::vector<std::string> SplitRawChatChunks(
    const std::string& text,
    size_t maxLength)
{
    std::vector<std::string> chunks;
    if (text.empty())
        return chunks;

    size_t start = 0;
    while (start < text.length())
    {
        size_t end = start + maxLength;
        if (end >= text.length())
        {
            chunks.push_back(text.substr(start));
            break;
        }

        size_t lastSpace = text.rfind(' ', end);
        if (lastSpace == std::string::npos || lastSpace <= start)
            lastSpace = end;

        chunks.push_back(text.substr(start, lastSpace - start));
        start = lastSpace;

        while (start < text.length() && text[start] == ' ')
            ++start;
    }

    return chunks;
}

static const std::string& GetGuideLink()
{
    static const std::string guideLink =
        "|Hplayer:" + GUIDE_NAME + "|h|cFF66AAFF[Azeroth Guide]|h|r";
    return guideLink;
}

static void SendGuideTextBlock(
    ChatHandler* handler,
    Player* player,
    const std::string& firstPrefix,
    const std::string& continuationPrefix,
    const std::string& normalizedText,
    const std::string& emptyFallback)
{
    std::string text = normalizedText.empty() ? emptyFallback : normalizedText;

    bool isFirstChunk = true;
    for (const std::string& rawChunk :
         SplitRawChatChunks(
             text,
             sLLMGuideConfig->GetMaxResponseLength()))
    {
        std::string line =
            (isFirstChunk ? firstPrefix : continuationPrefix) +
            ConvertGuideLinks(player, rawChunk);
        handler->SendSysMessage(line.c_str());
        isFirstChunk = false;
    }
}

// Build character context string
static std::string BuildCharacterContext(Player* player)
{
    std::ostringstream ctx;

    // Basic info: "Karaez is a level 19 Night Elf Hunter"
    ctx << player->GetName() << " is a level " << (int)player->GetLevel()
        << " " << GetRaceName(player->getRace())
        << " " << GetClassName(player->getClass());

    // Zone (use GetZoneId for main zone, not GetAreaId which returns subzones)
    if (AreaTableEntry const* area = sAreaTableStore.LookupEntry(player->GetZoneId()))
    {
        ctx << " in "
            << area->area_name[sWorld->GetDefaultDbcLocale()];
    }

    ctx << ". ";

    // Faction
    ctx << GetFaction(player->getRace()) << ". ";

    // Gold
    ctx << "Gold: " << FormatGold(player->GetMoney()) << ". ";

    // Honor and Arena points (if any)
    uint32 honor = player->GetHonorPoints();
    uint32 arena = player->GetArenaPoints();
    if (honor > 0 || arena > 0)
    {
        if (honor > 0)
            ctx << "Honor: " << honor;
        if (honor > 0 && arena > 0)
            ctx << ", ";
        if (arena > 0)
            ctx << "Arena: " << arena;
        ctx << ". ";
    }

    // Professions (primary and secondary)
    std::vector<std::string> profs;
    std::vector<std::string> secondaryProfs;
    for (uint32 i = 1; i < sSkillLineStore.GetNumRows(); ++i)
    {
        SkillLineEntry const* skill = sSkillLineStore.LookupEntry(i);
        if (!skill)
            continue;

        uint16 skillValue = player->GetSkillValue(skill->id);
        if (skillValue == 0)
            continue;

        std::ostringstream prof;
        prof << skill->name[0] << " (" << skillValue << ")";

        // Primary professions (categoryId == 11)
        if (skill->categoryId == SKILL_CATEGORY_PROFESSION)
        {
            profs.push_back(prof.str());
        }
        // Secondary professions (categoryId == 9): Fishing, Cooking, First Aid
        else if (skill->categoryId == SKILL_CATEGORY_SECONDARY)
        {
            secondaryProfs.push_back(prof.str());
        }
    }

    if (!profs.empty() || !secondaryProfs.empty())
    {
        ctx << "Professions: ";
        bool first = true;
        for (const auto& p : profs)
        {
            if (!first) ctx << ", ";
            ctx << p;
            first = false;
        }
        for (const auto& p : secondaryProfs)
        {
            if (!first) ctx << ", ";
            ctx << p;
            first = false;
        }
        ctx << ". ";
    }

    // Talent spec (e.g., "Beast Mastery (31/5/5)")
    std::string talentSpec = GetTalentSpec(player);
    if (!talentSpec.empty() && talentSpec != "No talents")
    {
        ctx << "Spec: " << talentSpec << ". ";
    }

    // Gear stats summary
    std::string equipment = GetEquipmentDetails(player);
    if (!equipment.empty())
    {
        ctx << equipment << ". ";
    }

    // Guild
    if (Guild* guild = sGuildMgr->GetGuildById(player->GetGuildId()))
    {
        ctx << "Guild: " << guild->GetName() << ". ";
    }

    // Group status
    if (Group* group = player->GetGroup())
    {
        if (group->isRaidGroup())
            ctx << "In a raid group. ";
        else
            ctx << "In a party. ";
    }
    else
    {
        ctx << "Solo. ";
    }

    // Current quests (all active quests)
    std::vector<std::string> quests;
    for (uint8 slot = 0; slot < MAX_QUEST_LOG_SIZE; ++slot)
    {
        uint32 questId = player->GetQuestSlotQuestId(slot);
        if (questId)
        {
            if (Quest const* quest = sObjectMgr->GetQuestTemplate(questId))
            {
                quests.push_back(quest->GetTitle());
            }
        }
    }

    if (!quests.empty())
    {
        ctx << "Active quests: ";
        for (size_t i = 0; i < quests.size(); ++i)
        {
            if (i > 0) ctx << ", ";
            ctx << quests[i];
        }
        ctx << ".";
    }

    return ctx.str();
}

// Submit a question to the LLM queue
// Returns true if question was submitted, false if rejected (cooldown, limit, etc.)
static bool SubmitQuestion(Player* player, const std::string& questionStr, bool isWhisper)
{
    if (!sLLMGuideConfig->IsEnabled())
    {
        ChatHandler(player->GetSession()).PSendSysMessage("LLM Chat is currently disabled.");
        return false;
    }

    if (questionStr.empty())
    {
        if (isWhisper)
            ChatHandler(player->GetSession()).PSendSysMessage("Just whisper your question to AzerothGuide!");
        else
            ChatHandler(player->GetSession()).PSendSysMessage("Usage: .ag <your question>");
        return false;
    }

    // Limit question length
    if (questionStr.length() > 500)
    {
        ChatHandler(player->GetSession()).PSendSysMessage("Question too long. Please keep it under 500 characters.");
        return false;
    }

    uint32 guid = player->GetGUID().GetCounter();

    // Check cooldown
    time_t now = time(nullptr);
    auto it = playerCooldowns.find(guid);
    if (it != playerCooldowns.end())
    {
        time_t elapsed = now - it->second;
        if (elapsed < sLLMGuideConfig->GetCooldownSeconds())
        {
            uint32 remaining = sLLMGuideConfig->GetCooldownSeconds() - elapsed;
            ChatHandler(player->GetSession()).PSendSysMessage("Please wait {} seconds before asking another question.", remaining);
            return false;
        }
    }

    // Check pending requests
    QueryResult pendingResult = CharacterDatabase.Query(
        "SELECT COUNT(*) FROM llm_guide_queue WHERE character_guid = {} AND status IN ('pending', 'processing')",
        guid);

    if (pendingResult)
    {
        uint32 pendingCount = (*pendingResult)[0].Get<uint32>();
        if (pendingCount >= sLLMGuideConfig->GetMaxPendingPerPlayer())
        {
            ChatHandler(player->GetSession()).PSendSysMessage("You have too many pending questions. Please wait for responses.");
            return false;
        }
    }

    // Build character context
    std::string characterContext = BuildCharacterContext(player);
    if (characterContext.length() > 500)
        characterContext = characterContext.substr(0, 497) + "...";
    std::string escapedContext = characterContext;
    CharacterDatabase.EscapeString(escapedContext);

    // Escape question
    std::string escapedQuestion = questionStr;
    CharacterDatabase.EscapeString(escapedQuestion);

    // Escape player name
    std::string escapedName = player->GetName();
    CharacterDatabase.EscapeString(escapedName);

    // Get player position for distance-based queries
    float posX = player->GetPositionX();
    float posY = player->GetPositionY();
    uint32 mapId = player->GetMapId();

    // Track active quest IDs separately so Python tools can exclude
    // already-in-progress quests without relying on truncated context.
    std::ostringstream activeQuestIds;
    bool firstQuestId = true;
    for (uint8 slot = 0; slot < MAX_QUEST_LOG_SIZE; ++slot)
    {
        uint32 questId = player->GetQuestSlotQuestId(slot);
        if (!questId)
            continue;

        if (!firstQuestId)
            activeQuestIds << ",";
        activeQuestIds << questId;
        firstQuestId = false;
    }

    // Numeric quest IDs only; safe to insert without string escaping.
    std::string activeQuestIdList = activeQuestIds.str();

    // Insert into queue
    CharacterDatabase.Execute(
        "INSERT INTO llm_guide_queue (character_guid, character_name, character_context, question, position_x, position_y, map_id, active_quest_ids, status, created_at) "
        "VALUES ({}, '{}', '{}', '{}', {}, {}, {}, '{}', 'pending', NOW())",
        guid,
        escapedName,
        escapedContext,
        escapedQuestion,
        posX,
        posY,
        mapId,
        activeQuestIdList);

    // Update cooldown
    playerCooldowns[guid] = now;

    // Send confirmation
    ChatHandler handler(player->GetSession());
    std::string youMsg = "|cFFFFFF00[You]: " + questionStr + "|r";
    handler.SendSysMessage(youMsg.c_str());
    handler.SendSysMessage("|cFF66AAFFProcessing your question...|r");

    LOG_DEBUG("module", "LLM Chat: Player {} asked (via {}): {}", player->GetName(), isWhisper ? "whisper" : "command", questionStr);

    return true;
}

static void PopulateHistoryEntryFromSummary(
    const std::string& summary,
    std::string& question,
    std::string& response)
{
    if (!question.empty() && !response.empty())
        return;

    if (summary.rfind("Q: ", 0) == 0)
    {
        size_t answerPos = summary.find(" | A: ");
        if (answerPos != std::string::npos)
        {
            if (question.empty())
                question = summary.substr(3, answerPos - 3);

            if (response.empty())
                response = summary.substr(answerPos + 6);

            return;
        }
    }

    LOG_DEBUG("module",
        "LLM Chat: Unrecognized history summary format for fallback: {}",
        summary);

    if (question.empty())
        question = summary;
}

static bool ShowHistory(
    ChatHandler* handler,
    Player* player,
    uint32 requestedCount,
    uint32 requestedPage)
{
    uint32 count = std::min(std::max(requestedCount, 1u), MAX_HISTORY_COUNT);
    uint32 guid = player->GetGUID().GetCounter();
    uint32 page = std::max(requestedPage, 1u);

    QueryResult countResult = CharacterDatabase.Query(
        "SELECT COUNT(*) FROM llm_guide_memory WHERE character_guid = {}",
        guid);

    uint32 totalCount = 0;
    if (countResult)
        totalCount = (*countResult)[0].Get<uint32>();

    if (totalCount == 0)
    {
        handler->PSendSysMessage(
            "{}: You don't have any saved conversation history yet.",
            GetGuideLink());
        return true;
    }

    uint32 totalPages = (totalCount + count - 1) / count;
    if (page > totalPages)
    {
        handler->PSendSysMessage(
            "{}: History page {} doesn't exist. "
            "Use .ag history page 1-{}.",
            GetGuideLink(),
            page,
            totalPages);
        return true;
    }

    uint32 offset = (page - 1) * count;

    // Command handlers take the simple synchronous path for now. If this
    // becomes hot or latency-sensitive, revisit with an async query flow.
    QueryResult result = CharacterDatabase.Query(
        "SELECT summary, question, response "
        "FROM llm_guide_memory "
        "WHERE character_guid = {} "
        "ORDER BY created_at DESC "
        "LIMIT {} OFFSET {}",
        guid,
        count,
        offset);

    if (!result)
    {
        handler->PSendSysMessage(
            "{}: Couldn't load that history page right now.",
            GetGuideLink());
        return true;
    }

    uint32 shownCount = static_cast<uint32>(result->GetRowCount());
    uint32 firstIndex = offset + 1;
    uint32 lastIndex = offset + shownCount;
    handler->PSendSysMessage(
        "{}: Showing conversations {}-{} of {} (page {}/{}).",
        GetGuideLink(),
        firstIndex,
        lastIndex,
        totalCount,
        page,
        totalPages);
    handler->SendSysMessage(
        "|cFF66AAFFUse .ag show <number> to view a full interaction.|r");
    if (page < totalPages)
    {
        handler->PSendSysMessage(
            "|cFF66AAFFNext page: .ag history page {}|r",
            page + 1);
    }

    uint32 index = firstIndex;
    do
    {
        Field* fields = result->Fetch();
        std::string summary = fields[0].Get<std::string>();
        std::string question = fields[1].Get<std::string>();
        std::string response = fields[2].Get<std::string>();

        PopulateHistoryEntryFromSummary(summary, question, response);

        std::string normalizedQuestion = NormalizeGuideText(question);
        normalizedQuestion = TruncateText(normalizedQuestion, 160);

        std::string formattedQuestion =
            ConvertGuideLinks(player, normalizedQuestion);

        if (formattedQuestion.empty())
            formattedQuestion = "(empty question)";

        handler->PSendSysMessage(
            "|cFF66AAFF{}.|r |cFFFFFF00Q:|r {}",
            index,
            formattedQuestion);
        ++index;
    } while (result->NextRow());

    return true;
}

static bool ShowHistoryEntry(
    ChatHandler* handler,
    Player* player,
    uint32 requestedIndex)
{
    uint32 guid = player->GetGUID().GetCounter();

    QueryResult result = CharacterDatabase.Query(
        "SELECT summary, question, response "
        "FROM llm_guide_memory "
        "WHERE character_guid = {} "
        "ORDER BY created_at DESC "
        "LIMIT 1 OFFSET {}",
        guid,
        requestedIndex - 1);

    if (!result)
    {
        handler->PSendSysMessage(
            "{}: No saved conversation found at index {}. "
            "Use .ag history to see available entries.",
            GetGuideLink(),
            requestedIndex);
        return true;
    }

    Field* fields = result->Fetch();
    std::string summary = fields[0].Get<std::string>();
    std::string question = fields[1].Get<std::string>();
    std::string response = fields[2].Get<std::string>();

    PopulateHistoryEntryFromSummary(summary, question, response);

    std::string normalizedQuestion = NormalizeGuideText(question);
    std::string normalizedResponse = NormalizeGuideText(response);

    handler->PSendSysMessage(
        "{}: Showing conversation {}.",
        GetGuideLink(),
        requestedIndex);
    SendGuideTextBlock(
        handler,
        player,
        "|cFFFFFF00Q:|r ",
        "   ",
        normalizedQuestion,
        "(empty question)");
    SendGuideTextBlock(
        handler,
        player,
        "|cFF66AAFFA:|r ",
        "   ",
        normalizedResponse,
        "(empty response)");
    return true;
}

static bool ClearHistory(ChatHandler* handler, Player* player)
{
    uint32 guid = player->GetGUID().GetCounter();

    // Best-effort pre-delete count for user feedback. A concurrent bridge
    // write could make the reported count slightly stale.
    QueryResult countResult = CharacterDatabase.Query(
        "SELECT COUNT(*) FROM llm_guide_memory WHERE character_guid = {}",
        guid);

    uint32 deletedCount = 0;
    if (countResult)
        deletedCount = (*countResult)[0].Get<uint32>();

    CharacterDatabase.Execute(
        "DELETE FROM llm_guide_memory WHERE character_guid = {}",
        guid);

    handler->PSendSysMessage(
        "{}: Cleared {} conversation {}.",
        GetGuideLink(),
        deletedCount,
        deletedCount == 1 ? "entry" : "entries");
    return true;
}

// Escape a C string for SQL output: doubles single
// quotes and backslashes.
static std::string EscapeSqlString(const char* str)
{
    std::string out;
    for (const char* p = str; *p; ++p)
    {
        if (*p == '\'')
            out += "''";
        else if (*p == '\\')
            out += "\\\\";
        else
            out += *p;
    }
    return out;
}

// GM-only: generate pre-computed NPC area SQL file.
// WARNING: This processes ~15-20k NPC spawns and may
// trigger map grid loading. It will block the world
// thread for several seconds. Only run on a dev server
// with no active players.
static bool GenerateNpcAreas(
    ChatHandler* handler, Player* player)
{
    if (!player->GetSession() ||
        player->GetSession()->GetSecurity()
            < SEC_GAMEMASTER)
    {
        handler->SendSysMessage(
            "This command requires GM privileges.");
        return true;
    }

    handler->SendSysMessage(
        "Generating NPC area data... "
        "this will block the server for several "
        "seconds. Do not run with players online.");

    // Query all NPC spawns on continent maps
    // with at least one service npcflag set
    QueryResult result = WorldDatabase.Query(
        "SELECT c.guid, c.id1, c.map, "
        "c.position_x, c.position_y, c.position_z "
        "FROM creature c "
        "JOIN creature_template ct "
        "ON ct.entry = c.id1 "
        "WHERE ct.npcflag > 0 "
        "AND c.map IN (0, 1, 530, 571) "
        "ORDER BY c.guid");

    if (!result)
    {
        handler->SendSysMessage(
            "No NPC spawns found. Aborting.");
        return true;
    }

    // Use enUS locale for deterministic output
    // regardless of server DBC.Locale setting
    static constexpr int LOCALE_INDEX = 0;

    // Create base maps for all 4 continents to
    // ensure grid terrain data is accessible.
    // CreateBaseMap will return existing or create new.
    static constexpr uint32 CONTINENT_MAPS[] =
        { 0, 1, 530, 571 };
    std::unordered_map<uint32, Map*> mapCache;
    for (uint32 mid : CONTINENT_MAPS)
    {
        Map* m = sMapMgr->CreateBaseMap(mid);
        if (!m)
        {
            handler->PSendSysMessage(
                "FATAL: Could not create base map "
                "for continent {}. Aborting.", mid);
            return true;
        }
        mapCache[mid] = m;
    }

    // Output path: module data directory (bind-mounted
    // in Docker, direct path for native builds)
    std::string sqlPath =
        sConfigMgr->GetOption<std::string>(
            "LLMGuide.GenerateAreas.OutputPath",
            "/azerothcore/modules/mod-llm-guide"
            "/data/sql/db-world/base"
            "/llm_guide_npc_areas.sql");

    std::ofstream outFile(sqlPath,
        std::ios::out | std::ios::trunc);
    if (!outFile.is_open())
    {
        handler->PSendSysMessage(
            "Failed to open output file: {}",
            sqlPath);
        return true;
    }

    // Write header
    outFile
        << "-- Auto-generated by .ag generate-areas\n"
        << "-- NPC subzone/area names for "
        << "mod-llm-guide\n"
        << "-- Locale: enUS\n\n"
        << "DROP TABLE IF EXISTS "
        << "`llm_guide_npc_areas`;\n"
        << "CREATE TABLE IF NOT EXISTS "
        << "`llm_guide_npc_areas` (\n"
        << "  `creature_guid` INT UNSIGNED "
        << "NOT NULL,\n"
        << "  `entry` INT UNSIGNED NOT NULL,\n"
        << "  `map_id` SMALLINT UNSIGNED "
        << "NOT NULL,\n"
        << "  `area_id` INT UNSIGNED NOT NULL,\n"
        << "  `area_name` VARCHAR(100) NOT NULL,\n"
        << "  `zone_id` INT UNSIGNED NOT NULL,\n"
        << "  `zone_name` VARCHAR(100) NOT NULL,\n"
        << "  PRIMARY KEY (`creature_guid`),\n"
        << "  KEY `idx_entry` (`entry`)\n"
        << ") ENGINE=InnoDB "
        << "COMMENT='Pre-computed subzone names "
        << "for NPC spawns';\n\n";

    uint32 totalRows = 0;
    uint32 resolved = 0;
    uint32 skipped = 0;
    uint32 batchCount = 0;
    static constexpr uint32 BATCH_SIZE = 500;
    static constexpr uint32 PROGRESS_INTERVAL = 5000;
    bool inInsert = false;

    do
    {
        Field* fields = result->Fetch();
        uint32 guid = fields[0].Get<uint32>();
        uint32 entry = fields[1].Get<uint32>();
        uint32 mapId = fields[2].Get<uint16>();
        float posX = fields[3].Get<float>();
        float posY = fields[4].Get<float>();
        float posZ = fields[5].Get<float>();

        ++totalRows;

        auto it = mapCache.find(mapId);
        if (it == mapCache.end() || !it->second)
        {
            ++skipped;
            continue;
        }

        uint32 areaId = it->second->GetAreaId(
            PHASEMASK_NORMAL, posX, posY, posZ);
        if (areaId == 0)
        {
            ++skipped;
            continue;
        }

        AreaTableEntry const* area =
            sAreaTableStore.LookupEntry(areaId);
        if (!area)
        {
            ++skipped;
            continue;
        }

        // Resolve area name (enUS)
        char const* areaName =
            area->area_name[LOCALE_INDEX];
        if (!areaName || areaName[0] == '\0')
        {
            ++skipped;
            continue;
        }

        // Resolve parent zone
        uint32 zoneId = area->zone;
        char const* zoneName = "";
        if (zoneId != 0)
        {
            AreaTableEntry const* zoneEntry =
                sAreaTableStore.LookupEntry(zoneId);
            if (zoneEntry)
            {
                zoneName =
                    zoneEntry->area_name[LOCALE_INDEX];
                if (!zoneName || zoneName[0] == '\0')
                    zoneName = "";
            }
        }
        else
        {
            // This IS a top-level zone
            zoneId = areaId;
            zoneName = areaName;
        }

        if (!zoneName)
            zoneName = "";

        std::string safeArea =
            EscapeSqlString(areaName);
        std::string safeZone =
            EscapeSqlString(zoneName);

        // Start new INSERT batch if needed
        if (batchCount == 0)
        {
            outFile
                << "INSERT INTO "
                << "`llm_guide_npc_areas` "
                << "(`creature_guid`, `entry`, "
                << "`map_id`, `area_id`, "
                << "`area_name`, `zone_id`, "
                << "`zone_name`) VALUES\n";
            inInsert = true;
        }
        else
        {
            outFile << ",\n";
        }

        outFile
            << "(" << guid
            << ", " << entry
            << ", " << mapId
            << ", " << areaId
            << ", '" << safeArea << "'"
            << ", " << zoneId
            << ", '" << safeZone << "')";

        ++batchCount;
        ++resolved;

        if (batchCount >= BATCH_SIZE)
        {
            outFile << ";\n\n";
            inInsert = false;
            batchCount = 0;
        }

        if (totalRows % PROGRESS_INTERVAL == 0)
        {
            handler->PSendSysMessage(
                "Processed {} spawns "
                "({} resolved, {} skipped)...",
                totalRows, resolved, skipped);
        }
    } while (result->NextRow());

    // Close any open INSERT
    if (inInsert && batchCount > 0)
    {
        outFile << ";\n";
    }

    outFile.close();

    handler->PSendSysMessage(
        "Done! {} spawns resolved, {} skipped "
        "out of {} total.",
        resolved, skipped, totalRows);
    handler->PSendSysMessage(
        "SQL file written to: {}", sqlPath);
    return true;
}

static bool TryHandleAgAliasCommand(
    ChatHandler* handler,
    Player* player,
    const std::string& questionStr)
{
    std::string input = CollapseWhitespace(questionStr);
    uint32 parsedCount = 0;
    uint32 parsedPage = 0;

    if (input == "clear")
        return ClearHistory(handler, player);

    if (input == "generate-areas")
        return GenerateNpcAreas(handler, player);

    if (TryParseHistoryArguments(input, parsedCount, parsedPage))
    {
        return ShowHistory(handler, player, parsedCount, parsedPage);
    }

    if (input == "show")
    {
        handler->SendSysMessage("Usage: .ag show <number>");
        return true;
    }

    std::string showTail;
    if (SplitCommandTail(input, "show ", showTail))
    {
        uint32 parsedIndex = 0;
        if (!TryParsePositiveUInt32(showTail, parsedIndex))
            return false;

        return ShowHistoryEntry(handler, player, parsedIndex);
    }

    return false;
}

class LLMGuide_CommandScript : public CommandScript
{
public:
    LLMGuide_CommandScript() : CommandScript("LLMGuide_CommandScript") {}

    ChatCommandTable GetCommands() const override
    {
        static ChatCommandTable commandTable =
        {
            { "ag", HandleAskCommand, SEC_PLAYER, Console::No },  // Shortcut: .ag
        };

        return commandTable;
    }

    static bool HandleAskCommand(ChatHandler* handler, Tail question)
    {
        Player* player = handler->GetSession()->GetPlayer();
        if (!player)
            return false;

        std::string questionStr = std::string(question);

        if (TryHandleAgAliasCommand(handler, player, questionStr))
            return true;

        SubmitQuestion(player, questionStr, false);
        return true;
    }

};

class LLMGuide_WorldScript : public WorldScript
{
public:
    LLMGuide_WorldScript()
        : WorldScript(
              "LLMGuide_WorldScript",
              {WORLDHOOK_ON_AFTER_CONFIG_LOAD,
               WORLDHOOK_ON_STARTUP,
               WORLDHOOK_ON_UPDATE}) {}

    void OnAfterConfigLoad(bool /*reload*/) override
    {
        sLLMGuideConfig->LoadConfig();
    }

    void OnStartup() override
    {
        if (!sLLMGuideConfig->IsEnabled())
            return;

        // Clear any stale pending/processing requests from previous session
        CharacterDatabase.Execute(
            "UPDATE llm_guide_queue SET status = 'cancelled' "
            "WHERE status IN ('pending', 'processing')");

        LOG_INFO("module", "LLM Chat: Cleared stale requests, WorldScript initialized");
    }

    void OnUpdate(uint32 diff) override
    {
        if (!sLLMGuideConfig->IsEnabled())
            return;

        static uint32 timer = 0;
        static uint32 cleanupTimer = 0;
        timer += diff;
        cleanupTimer += diff;

        // Cleanup stale cooldown entries every 5 minutes
        if (cleanupTimer >= 300000)  // 5 minutes in ms
        {
            cleanupTimer = 0;
            time_t now = time(nullptr);
            uint32 cooldownSecs = sLLMGuideConfig->GetCooldownSeconds();

            for (auto it = playerCooldowns.begin(); it != playerCooldowns.end();)
            {
                if (now - it->second > cooldownSecs * 2)  // Remove if 2x past cooldown
                    it = playerCooldowns.erase(it);
                else
                    ++it;
            }
        }

        if (timer < sLLMGuideConfig->GetPollIntervalMs())
            return;

        timer = 0;

        // Atomically mark rows as 'delivered' to prevent duplicate processing
        CharacterDatabase.DirectExecute(
            "UPDATE llm_guide_queue SET status = 'delivered' "
            "WHERE status = 'complete' LIMIT 5");

        // Now fetch the rows we just marked
        QueryResult result = CharacterDatabase.Query(
            "SELECT id, character_guid, character_name, response FROM llm_guide_queue "
            "WHERE status = 'delivered'");

        if (!result)
            return;

        do
        {
            Field* fields = result->Fetch();
            uint32 id = fields[0].Get<uint32>();
            uint32 characterGuid = fields[1].Get<uint32>();
            std::string characterName = fields[2].Get<std::string>();
            std::string response = fields[3].Get<std::string>();

            // Find the player and send response
            Player* player = ObjectAccessor::FindPlayerByName(characterName);
            if (player && player->GetGUID().GetCounter() == characterGuid)
            {
                SendChunkedResponse(player, response);
                // Only delete after successful delivery
                CharacterDatabase.DirectExecute("DELETE FROM llm_guide_queue WHERE id = {}", id);
            }
            // If player is offline, row remains for delivery when they log back in

        } while (result->NextRow());
    }

private:
    void SendChunkedResponse(Player* player, const std::string& response)
    {
        const uint32 maxLen = sLLMGuideConfig->GetMaxResponseLength();
        ChatHandler handler(player->GetSession());

        std::string normalizedResponse = NormalizeGuideText(response);

        if (normalizedResponse.length() <= maxLen)
        {
            handler.PSendSysMessage(
                "{}: {}",
                GetGuideLink(),
                ConvertGuideLinks(player, normalizedResponse));
            return;
        }

        int chunkNum = 1;
        for (const std::string& rawChunk :
             SplitRawChatChunks(normalizedResponse, maxLen))
        {
            handler.PSendSysMessage(
                "{} [{}]: {}",
                GetGuideLink(),
                chunkNum,
                ConvertGuideLinks(player, rawChunk));
            chunkNum++;
        }
    }
};

// ServerScript to intercept whispers to "AzerothGuide"
class LLMGuide_ServerScript : public ServerScript
{
public:
    LLMGuide_ServerScript() : ServerScript("LLMGuide_ServerScript", {SERVERHOOK_CAN_PACKET_RECEIVE}) {}

    bool CanPacketReceive(
        WorldSession* session,
        WorldPacket const& packet) override
    {
        if (!sLLMGuideConfig->IsEnabled())
            return true;

        if (packet.GetOpcode() != CMSG_MESSAGECHAT)
            return true;

        // Minimum packet size:
        // type(4) + lang(4) + at least 1 byte
        if (packet.size() < 9)
            return true;

        // Packet is const — make a local copy to
        // parse without affecting the original.
        WorldPacket copy(packet);

        try
        {
            uint32 type;
            uint32 lang;
            copy >> type >> lang;

            if (type != CHAT_MSG_WHISPER)
                return true;

            std::string to;
            copy >> to;

            std::string msg =
                copy.ReadCString(lang != LANG_ADDON);

            // Case-insensitive comparison
            std::string toLower = to;
            std::transform(
                toLower.begin(), toLower.end(),
                toLower.begin(), ::tolower);

            if (toLower != GUIDE_NAME_LOWER)
                return true;

            Player* player = session->GetPlayer();
            if (!player)
                return true;

            LOG_DEBUG("module",
                "LLM Chat: {} whispered to "
                "AzerothGuide: {}",
                player->GetName(), msg);

            SubmitQuestion(player, msg, true);

            // Return false to prevent
            // "Player not found" error
            return false;
        }
        catch (const ByteBufferException&)
        {
            return true;
        }
    }
};

// PlayerScript to clear conversation memory on login
class LLMGuide_PlayerScript : public PlayerScript
{
public:
    LLMGuide_PlayerScript() : PlayerScript("LLMGuide_PlayerScript", {PLAYERHOOK_ON_LOGIN}) {}

    void OnPlayerLogin(Player* player) override
    {
        if (!sLLMGuideConfig->IsEnabled())
            return;

        uint32 guid = player->GetGUID().GetCounter();

        // Clear conversation memory for this character - fresh start each session
        // Done on login to ensure clean slate even after crashes/disconnects
        CharacterDatabase.Execute(
            "DELETE FROM llm_guide_memory WHERE character_guid = {}",
            guid);

        // Also clear from cooldown map
        playerCooldowns.erase(guid);

        LOG_DEBUG("module", "LLM Chat: Cleared conversation memory for {} on login", player->GetName());
    }
};

void AddLLMGuideScripts()
{
    new LLMGuide_CommandScript();
    new LLMGuide_WorldScript();
    new LLMGuide_ServerScript();
    new LLMGuide_PlayerScript();
}

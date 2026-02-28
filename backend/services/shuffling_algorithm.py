"""
Smart Group Shuffling Algorithm
Balances groups by skills, roles, and diversity
"""
from collections import Counter
import random


def parse_skills(skills_string):
    """Parse comma-separated skills into a list"""
    if not skills_string:
        return []
    return [skill.strip().lower() for skill in skills_string.split(",")]


def calculate_role_diversity_score(group_roles):
    """
    Calculate diversity score for roles in a group.
    Higher score = more diverse roles (less duplication)
    Range: 0-1, where 1 = perfect diversity
    """
    if not group_roles:
        return 0
    role_counts = Counter(group_roles)
    total_roles = len(group_roles)
    
    # Calculate uniqueness: 1 - (duplicate_penalty)
    diversity = 1 - (sum(count - 1 for count in role_counts.values()) / total_roles)
    return diversity


def calculate_skill_overlap(group_skills_list):
    """
    Calculate skill overlap in a group.
    Lower overlap = more unique skills, which is good
    Range: 0-1, where 0 = no overlap (ideal)
    """
    if not group_skills_list or len(group_skills_list) <= 1:
        return 0
    
    all_skills = []
    for skills in group_skills_list:
        all_skills.extend(skills)
    
    if not all_skills:
        return 0
    
    skill_counts = Counter(all_skills)
    total_skills = len(all_skills)
    
    # Overlap penalty: how many duplicate skills exist
    overlap = sum(count - 1 for count in skill_counts.values()) / total_skills
    return overlap


def calculate_group_balance_score(group_members):
    """
    Calculate overall balance score for a group (0-100)
    Considers: role diversity, skill uniqueness, group size
    """
    if not group_members:
        return 0
    
    roles = [m.get("role", "Unknown") for m in group_members]
    skills_list = [parse_skills(m.get("skills", "")) for m in group_members]
    
    role_diversity = calculate_role_diversity_score(roles)
    skill_overlap = calculate_skill_overlap(skills_list)
    
    # Score = (role diversity + (1 - skill overlap)) / 2 * 100
    score = ((role_diversity + (1 - skill_overlap)) / 2) * 100
    return round(score, 2)


def shuffle_into_groups(profiles, num_groups=4, group_size=4):
    """
    Intelligently shuffle students into balanced groups
    
    Args:
        profiles: List of student profile dicts
        num_groups: Number of groups to create
        group_size: Target size per group
    
    Returns:
        List of groups with balanced members
    """
    if not profiles or len(profiles) < num_groups:
        return []
    
    # Start with random shuffle
    shuffled = profiles.copy()
    random.shuffle(shuffled)
    
    # Create initial groups
    groups = [[] for _ in range(num_groups)]
    for i, student in enumerate(shuffled):
        groups[i % num_groups].append(student)
    
    # Optimize groups with multiple passes
    for iteration in range(5):  # 5 optimization passes
        improved = False
        
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                # Try swapping students between groups i and j
                if len(groups[i]) > 0 and len(groups[j]) > 0:
                    original_score_i = calculate_group_balance_score(groups[i])
                    original_score_j = calculate_group_balance_score(groups[j])
                    original_total = original_score_i + original_score_j
                    
                    # Try swapping each pair
                    for idx_i in range(len(groups[i])):
                        for idx_j in range(len(groups[j])):
                            # Swap
                            groups[i][idx_i], groups[j][idx_j] = groups[j][idx_j], groups[i][idx_i]
                            
                            new_score_i = calculate_group_balance_score(groups[i])
                            new_score_j = calculate_group_balance_score(groups[j])
                            new_total = new_score_i + new_score_j
                            
                            # Keep swap if better
                            if new_total > original_total:
                                improved = True
                            else:
                                # Swap back
                                groups[i][idx_i], groups[j][idx_j] = groups[j][idx_j], groups[i][idx_i]
        
        if not improved:
            break  # No improvements found, stop optimizing
    
    # Format output
    result_groups = []
    for idx, group in enumerate(groups):
        if group:  # Only include non-empty groups
            group_data = {
                "id": idx + 1,
                "name": f"Group {idx + 1}",
                "members": [m["email"] for m in group],
                "balance_score": calculate_group_balance_score(group),
                "member_details": group
            }
            result_groups.append(group_data)
    
    return result_groups


def suggest_group_improvements(groups_data):
    """
    Analyze groups and suggest improvements
    
    Returns list of suggestions for balancing
    """
    suggestions = []
    
    # Find groups with imbalanced scores
    scores = [g.get("balance_score", 0) for g in groups_data]
    avg_score = sum(scores) / len(scores) if scores else 0
    
    for idx, group in enumerate(groups_data):
        score = group.get("balance_score", 0)
        if score < avg_score - 10:
            suggestions.append({
                "group_id": group.get("id"),
                "issue": "Low diversity - consider swapping members with higher-scoring groups",
                "current_score": score,
                "target_score": round(avg_score, 2)
            })
    
    return suggestions

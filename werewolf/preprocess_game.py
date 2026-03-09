"""
Preprocess a raw Werewolf game JSON into a compact replay format.
Extracts: players, roles, phases, chat messages, reasoning, votes, night actions, deaths.
"""
import json
import sys

def preprocess_game(raw_path, output_path=None):
    with open(raw_path) as f:
        game = json.load(f)
    
    game_id = game.get('id', 'unknown')
    agents_info = game.get('info', {}).get('Agents', [])
    steps = game['steps']
    rewards = game.get('rewards', [])
    
    # Build agent index -> name/model mapping
    # First, figure out player_id -> agent_index mapping from observations
    player_to_index = {}
    player_roles = {}
    player_models = {}
    
    for step in steps:
        for idx, agent in enumerate(step):
            obs = agent.get('observation', {}).get('raw_observation', {})
            if obs and 'player_id' in obs:
                pid = obs['player_id']
                if pid not in player_to_index:
                    player_to_index[pid] = idx
                    player_roles[pid] = obs.get('role', 'Unknown')
                    if idx < len(agents_info):
                        player_models[pid] = agents_info[idx].get('Name', 'Unknown')
    
    # Build player list
    players = []
    for pid, idx in sorted(player_to_index.items(), key=lambda x: x[1]):
        players.append({
            'id': pid,
            'model': player_models.get(pid, 'Unknown'),
            'role': player_roles.get(pid, 'Unknown'),
            'reward': rewards[idx] if idx < len(rewards) else 0
        })
    
    # Determine winner
    ww_reward = sum(p['reward'] for p in players if p['role'] == 'Werewolf')
    winner = 'Werewolves' if ww_reward > 0 else 'Villagers'
    
    # Extract timeline events
    timeline = []
    seen_events = set()  # dedup
    
    for step_idx, step in enumerate(steps):
        for agent_idx, agent in enumerate(step):
            action = agent.get('action', {})
            obs = agent.get('observation', {}).get('raw_observation', {})
            
            if not obs or not isinstance(obs, dict):
                continue
            
            pid = obs.get('player_id', '')
            phase = obs.get('detailed_phase', '')
            day = obs.get('day', 0)
            
            # Extract chat messages with reasoning
            if isinstance(action, dict) and action.get('action_type') == 'ChatAction':
                kwargs = action.get('kwargs', {})
                msg = kwargs.get('message', '')
                reasoning = kwargs.get('reasoning', '')
                if msg:
                    event_key = f"chat_{day}_{pid}_{msg[:50]}"
                    if event_key not in seen_events:
                        seen_events.add(event_key)
                        timeline.append({
                            'type': 'chat',
                            'day': day,
                            'phase': kwargs.get('phase', phase),
                            'player': pid,
                            'message': msg,
                            'reasoning': reasoning,
                            'threat_level': kwargs.get('perceived_threat_level', '')
                        })
            
            # Extract votes
            if isinstance(action, dict) and action.get('action_type') == 'VoteAction':
                kwargs = action.get('kwargs', {})
                target = kwargs.get('target_id', '')
                reasoning = kwargs.get('reasoning', '')
                if target:
                    event_key = f"vote_{day}_{pid}_{target}"
                    if event_key not in seen_events:
                        seen_events.add(event_key)
                        timeline.append({
                            'type': 'vote',
                            'day': day,
                            'phase': phase,
                            'player': pid,
                            'target': target,
                            'reasoning': reasoning
                        })
            
            # Extract night actions (kill, inspect, heal)
            if isinstance(action, dict) and action.get('action_type') in ('EliminateProposalAction', 'InspectAction', 'HealAction'):
                kwargs = action.get('kwargs', {})
                target = kwargs.get('target_id', '')
                reasoning = kwargs.get('reasoning', '')
                action_type = action['action_type'].replace('Action', '').replace('Proposal', '')
                event_key = f"night_{day}_{pid}_{action_type}_{target}"
                if event_key not in seen_events:
                    seen_events.add(event_key)
                    timeline.append({
                        'type': 'night_action',
                        'day': day,
                        'phase': 'Night',
                        'player': pid,
                        'action': action_type,
                        'target': target,
                        'reasoning': reasoning
                    })
            
            # Extract announcements (deaths, reveals, etc)
            events = obs.get('new_player_event_views', [])
            for ev in events:
                ename = ev.get('event_name', '')
                desc = ev.get('description', '')
                eday = ev.get('day', day)
                ephase = ev.get('phase', '')
                
                if ename in ('vote_result', 'exile_result', 'elimination_result', 'game_end'):
                    event_key = f"ann_{eday}_{ename}_{desc[:50]}"
                    if event_key not in seen_events:
                        seen_events.add(event_key)
                        data = ev.get('data', {})
                        timeline.append({
                            'type': 'announcement',
                            'day': eday,
                            'phase': ephase,
                            'event': ename,
                            'description': desc,
                            'data': {k: v for k, v in data.items() if isinstance(v, (str, int, bool, type(None)))}
                        })
    
    # Sort timeline by day, then by type priority
    type_order = {'night_action': 0, 'announcement': 1, 'chat': 2, 'vote': 3}
    timeline.sort(key=lambda e: (e['day'], 0 if 'Night' in str(e.get('phase', '')) else 1, type_order.get(e['type'], 5)))
    
    result = {
        'id': game_id,
        'game_number': raw_path.split('/')[-1].replace('.json', ''),
        'players': players,
        'winner': winner,
        'total_days': max((e['day'] for e in timeline), default=0),
        'timeline': timeline
    }
    
    if output_path:
        with open(output_path, 'w') as f:
            json.dump(result, f, indent=None, separators=(',', ':'))
    
    # Stats
    chats = sum(1 for e in timeline if e['type'] == 'chat')
    votes = sum(1 for e in timeline if e['type'] == 'vote')
    nights = sum(1 for e in timeline if e['type'] == 'night_action')
    anns = sum(1 for e in timeline if e['type'] == 'announcement')
    print(f"Game {result['game_number']}: {len(players)} players, {result['total_days']} days, {winner}")
    print(f"  {chats} chats, {votes} votes, {nights} night actions, {anns} announcements")
    print(f"  Total events: {len(timeline)}")
    
    return result

if __name__ == '__main__':
    raw = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else None
    result = preprocess_game(raw, out)
    if out:
        import os
        size = os.path.getsize(out)
        print(f"  Output: {out} ({size/1024:.1f} KB)")


insert into client_lens (client, weights, half_life_days, min_score)
values ('byosync', '{"source":"config/signals.yaml"}'::jsonb, 30, 0.45)
on conflict (client) do nothing;

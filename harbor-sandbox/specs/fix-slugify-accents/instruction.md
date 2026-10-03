# Les URLs des articles en français sont tronquées

Les titres contenant des lettres accentuées donnent des slugs illisibles : « Café Crème » devient `caf-cr-me` au lieu de `cafe-creme`. Les accents devraient simplement être retirés (é → e, à → a, ç → c, etc.), pas traités comme des séparateurs.

Le code se trouve dans `/app`. Corrige le comportement sans casser l'existant.

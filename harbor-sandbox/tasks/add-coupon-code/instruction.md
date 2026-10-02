# Ajouter la prise en charge des codes promo dans le panier

Le marketing veut lancer deux codes promo. Le panier doit offrir une méthode `Cart.apply_coupon(code: str)` :

- `WELCOME10` : 10 % de réduction sur le total du panier ;
- `SAVE5` : 5,00 de réduction fixe sur le total du panier.

Règles :

- la réduction s'applique **après** les remises volume existantes ;
- un seul code actif à la fois : un nouvel appel à `apply_coupon` remplace le précédent ;
- un code inconnu lève `ValueError` et laisse le code déjà actif inchangé ;
- les codes sont insensibles à la casse (`welcome10` fonctionne) ;
- le total ne descend jamais sous `0.00` ;
- l'arrondi (au centime, half-up) se fait une seule fois, à la fin.

Sans code promo, le comportement actuel de `Cart.total()` ne change pas. Le code se trouve dans `/app`.

# La dernière page d'une liste paginée est introuvable

Sur l'écran de commandes, une liste de 25 éléments à raison de 10 par page affiche « 2 pages » et la page 3 (5 éléments) renvoie une erreur. Les derniers éléments sont donc inaccessibles. Le même problème apparaît dès que le nombre d'éléments n'est pas un multiple exact de la taille de page.

Le code se trouve dans `/app`. Corrige le comportement sans casser l'existant.

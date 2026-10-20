# T2S Group Holding — nombre d'actions (question non envoyée)

**Constat (20/10/2026).**
- La liste des émetteurs de la Bourse de Casablanca donne **22 584 118** titres (`datasets/bourse_emetteurs.json`).
- Nos pièces donnent **21 785 174** :
  - 10 107 834 actions au 30/06/2026 (S1 p.21) ;
  - × 2 par division du nominal ;
  - + 1 569 506 actions nouvelles de l'introduction en bourse (communiqué des résultats définitifs, AMMC, p.1).
  - La capitalisation publiée par l'opérateur divisée par le cours redonne ce même chiffre.
- Écart : **798 944 titres (3,7 %)**.

**Cause identifiée (20/10/2026, verificateur-finance).** L'écart est exactement
l'« Augmentation de Capital Dirigeant » décrite au document de référence
(https://www.ammc.ma/sites/default/files/T2S_IPO_DR_010_2026.pdf) :
- p.37 : « l'Augmentation de Capital Dirigeant serait réalisée par émission de 798 944 actions à un prix de
  souscription de 178,40 dirhams, correspondant au prix de souscription de l'IPO, soit 223 dirhams assorti
  d'une décote de 20% » ;
- p.258 (acte d'engagement du souscripteur) : « souscrire à l'intégralité des actions nouvelles qui seront
  émises dans le cadre de l'Augmentation de Capital Dirigeant, soit un nombre de 798 944 actions nouvelles
  […] sous la condition suspensive de la réalisation définitive de l'IPO » ; et « le calendrier définitif de
  réalisation de l'Augmentation de Capital Dirigeant sera arrêté en concertation avec l'Autorité Marocaine
  du Marché des Capitaux » ;
- 21 785 174 + 798 944 = 22 584 118 : le chiffre de la liste des émetteurs, au titre près.

**Ce qui manque : la DATE.** Aucune pièce lue ne donne d'avis de réalisation daté de cette augmentation
(AGE prévue le 17/08/2026, p.37). Sans date, on ne sait pas depuis quelle séance le nombre coté est
22 584 118.

**Question.** À quelle date l'Augmentation de Capital Dirigeant (798 944 actions) a-t-elle été réalisée,
et sur quel avis (AMMC ou Bourse de Casablanca) ?

**En attendant :** aucune correction. Le chiffre de 21 785 174, établi sur pièce, est conservé (R11) :
une opération sur titres se constate sur pièce datée, elle ne se déduit pas d'un écart. Effet si elle
était constatée : BPA 12 mois 187,019 ÷ 22 584 118 = 8,28 au lieu de 8,58.

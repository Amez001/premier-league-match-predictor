import { useEffect, useState } from 'react'
import type { BacktestRow, Meta } from '../api'
import { Tex } from '../components/Tex'
import { int, longDate, num2, pct } from '../format'

const MODEL_NAMES: Record<string, string> = {
  elo_logistic: 'Elo + régression logistique',
  baseline_logistic: 'Régression logistique (forme, classement, Elo)',
  random_forest: 'Random Forest',
  xgboost: 'XGBoost',
  poisson: 'Poisson (modèle de buts)',
  naive_base_rate: 'Fréquences historiques (référence)',
}

const SECTIONS = [
  ['principe', 'Le principe'],
  ['donnees', 'Les données'],
  ['elo', 'Le rating Elo'],
  ['poisson', 'Le modèle de buts'],
  ['buteurs', 'Les buteurs'],
  ['simulation', 'La simulation de saison'],
  ['trophees', 'Buteur et passeur'],
  ['validation', 'La validation'],
  ['bilan', 'Le bilan de la saison'],
  ['limites', 'Les limites'],
] as const

const PIPELINE = [
  ['Données', 'Résultats depuis 2000, effectifs de la saison'],
  ['Notes', 'Elo de chaque club, attaque et défense'],
  ['Modèles', 'Issue du match, score exact, buteurs'],
  ['Simulation', '10 000 fins de saison'],
  ['Validation', 'Test sur des saisons jamais vues'],
]

/** Highlights the section currently in view in the table of contents. */
function useActiveSection(ids: readonly string[]) {
  const [active, setActive] = useState<string>(ids[0])
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)
        if (visible[0]) setActive(visible[0].target.id)
      },
      { rootMargin: '-80px 0px -60% 0px' },
    )
    ids.forEach((id) => {
      const el = document.getElementById(id)
      if (el) observer.observe(el)
    })
    return () => observer.disconnect()
  }, [ids])
  return active
}

const SECTION_IDS = SECTIONS.map(([id]) => id)

export function HowItWorksPage({ meta, backtest }: { meta: Meta | null; backtest: BacktestRow[] }) {
  const rows = [...backtest].sort((a, b) => parseFloat(a.log_loss) - parseFloat(b.log_loss))
  const best = rows[0]
  const reference = rows.find((r) => r.model === 'naive_base_rate')
  const active = useActiveSection(SECTION_IDS)

  return (
    <div className="page">
      <header className="page-header">
        <h1>Méthode</h1>
        <p className="standfirst">
          Comment le site passe de vingt-cinq ans de résultats à des probabilités de match, de score, de buteur et de
          classement, et comment on vérifie qu'elles tiennent la route.
        </p>
      </header>

      <div className="doc-layout">
        <nav className="toc" aria-label="Sommaire">
          <ol>
            {SECTIONS.map(([id, label], i) => (
              <li key={id}>
                <a
                  href={`#/methode/${id}`}
                  className={active === id ? 'is-active' : ''}
                  onClick={(e) => (e.preventDefault(), document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' }))}
                >
                  <span className="toc-n tabular">{String(i + 1).padStart(2, '0')}</span>
                  {label}
                </a>
              </li>
            ))}
          </ol>
        </nav>

        <article className="doc">
          <section id="principe">
            <h2>Le principe</h2>
            <ol className="pipeline">
              {PIPELINE.map(([title, text], i) => (
                <li key={title}>
                  <span className="pipeline-n tabular">{String(i + 1).padStart(2, '0')}</span>
                  <strong>{title}</strong>
                  <span>{text}</span>
                </li>
              ))}
            </ol>
            <p>
              Chaque chiffre du site est une probabilité. « Arsenal gagne » ne se vérifie qu'à moitié ; « Arsenal 58 %,
              nul 25 %, Liverpool 17 % » se confronte à des milliers de matchs réels, et c'est sur cette base que les
              modèles sont comparés.
            </p>
          </section>

          <section id="donnees">
            <h2>Les données</h2>
            <p>
              Les résultats viennent de <a href="https://www.football-data.co.uk/englandm.php">football-data.co.uk</a>, un
              fichier par saison
              {meta && (
                <>
                  , soit {int(meta.n_matches_history)} matchs de {meta.first_season} à aujourd'hui. Le dernier match pris en
                  compte date du {longDate(meta.last_match_date)}
                </>
              )}
              .
            </p>
            <p>
              Les effectifs et les buts des joueurs viennent de <a href="https://fbref.com/">FBref</a>, via la librairie{' '}
              <code>soccerdata</code>
              {meta?.players_snapshot_date && <> (relevé du {longDate(meta.players_snapshot_date)})</>}. Les vingt équipes
              proposées sont celles de la saison en cours, déduite de la date du jour.
            </p>
            <p>Une tâche automatique met à jour le dépôt chaque mercredi soir : résultats, effectifs et backtest.</p>
          </section>

          <section id="elo">
            <h2>Le rating Elo</h2>
            <p>
              Chaque club part de 1 500 points. Avant un match, l'écart de notes, avantage du terrain compris (
              <Tex>{'H = 60'}</Tex>), donne un score attendu pour l'équipe à domicile :
            </p>
            <Tex display>{'E_{dom} = \\frac{1}{1 + 10^{-(R_{dom} + H - R_{ext})/400}}'}</Tex>
            <p>
              Après le match, chaque note bouge selon l'écart entre le résultat <Tex>{'S'}</Tex> (1, ½ ou 0) et ce score
              attendu. Le multiplicateur <Tex>{'M'}</Tex> fait peser davantage les larges victoires :
            </p>
            <Tex display>{"R'_{dom} = R_{dom} + K \\cdot M \\cdot (S - E_{dom}), \\qquad K = 20"}</Tex>
            <p>
              Une régression logistique multinomiale, ajustée sur vingt-cinq ans de matchs, traduit ensuite l'écart de
              notes en probabilités de victoire, de nul et de défaite. Ce sont les trois pourcentages de la page Match.
            </p>
            <Tex display>{'P(Y = k) = \\frac{e^{\\beta_{k0} + \\beta_{k1}\\,\\Delta\\text{Elo}}}{\\sum_j e^{\\beta_{j0} + \\beta_{j1}\\,\\Delta\\text{Elo}}}, \\quad k \\in \\{\\text{dom}, \\text{nul}, \\text{ext}\\}'}</Tex>
          </section>

          <section id="poisson">
            <h2>Le modèle de buts</h2>
            <p>
              Pour le score exact, les buts de chaque équipe suivent une loi de Poisson dont la moyenne dépend de sa propre
              attaque et de la défense adverse :
            </p>
            <Tex display>{'\\begin{aligned} \\text{Buts}_{dom} &\\sim \\text{Poisson}(\\lambda_{dom}) \\\\ \\log \\lambda_{dom} &= \\mu + \\text{avantage} + \\text{attaque}_{dom} - \\text{défense}_{ext} \\end{aligned}'}</Tex>
            <p>La probabilité d'un score est le produit des deux lois :</p>
            <Tex display>{'P(i\\text{–}j) = \\frac{\\lambda_{dom}^{\\,i} e^{-\\lambda_{dom}}}{i!} \\cdot \\frac{\\lambda_{ext}^{\\,j} e^{-\\lambda_{ext}}}{j!}'}</Tex>
            <p>
              Deux précautions, réglées sur les saisons 2008 à 2012, qui précèdent toutes les saisons de test. D'abord, un
              match compte deux fois moins par année d'ancienneté (<Tex>{'w = 0{,}5^{\\,\\text{âge}/365}'}</Tex>) : sans
              cela, un club promu serait jugé sur sa dernière saison en Premier League, parfois vieille de vingt-cinq ans.
              Ensuite, une pénalité ramène vers la moyenne de la ligue les équipes sur lesquelles on a peu de matchs
              récents.
            </p>
            <p>
              Cette pénalité a été revue en cours de route. Une première version projetait un promu à 21 points après un
              mauvais mois : cinq matchs suffisaient à fixer sa note. Le backtest n'évaluait le modèle qu'avant chaque
              saison, jamais en cours de saison comme ici. Réévaluée avec un réentraînement chaque semaine, la log loss sur
              les matchs de début de saison est passée de 0,999 à 0,980.
            </p>
          </section>

          <section id="buteurs">
            <h2>Les buteurs</h2>
            <p>
              La plupart des joueurs marquent trop peu pour être modélisés seuls. Les buts attendus de l'équipe sont donc
              répartis entre ses joueurs, selon une part qui mêle les buts de la saison et un a priori tiré du poste et du
              temps de jeu, pondéré par <Tex>{'K = 8'}</Tex> buts fictifs :
            </p>
            <Tex display>{'\\text{part}_i = \\frac{\\text{buts}_i + K \\cdot \\text{a priori}_i}{\\text{buts}_{équipe} + K}'}</Tex>
            <p>
              En début de saison, l'a priori pèse lourd : quatre buts en cinq matchs ne valent pas 60 % de l'attaque d'une
              équipe. À mi-saison, les buts réels l'emportent. Seuls les buts marqués par les joueurs du club sont
              répartis : environ 4 % des buts d'une équipe sont des buts contre son camp de joueurs adverses. Cette proportion,{' '}
              <Tex>{'\\rho \\approx 0{,}96'}</Tex>, est mesurée sur toute la saison précédente, plus stable que les
              premières journées :
            </p>
            <Tex display>{'\\lambda_i = \\lambda_{équipe} \\cdot \\rho \\cdot \\text{part}_i, \\qquad P(\\text{marque}) = 1 - e^{-\\lambda_i}'}</Tex>
            <p>
              Une première version ajoutait un bonus de forme récente : la part d'un joueur qui venait d'enchaîner les
              buts pouvait presque doubler. Le bilan de la saison l'a démenti. Sur les journées 2 à 5 de 2026-27, le buteur
              favori de chaque équipe a marqué 16 fois pour 25 attendus. Une semaine de matchs est un échantillon trop petit
              pour qu'une série veuille dire quelque chose. Sans ce bonus, les mêmes matchs donnent 17 buts pour 22
              attendus, dans la fourchette normale.
            </p>
          </section>

          <section id="simulation">
            <h2>La simulation de saison</h2>
            <ol className="steps">
              <li>Le classement actuel est calculé à partir des matchs déjà joués.</li>
              <li>
                Les matchs restants se déduisent sans calendrier externe : chaque club reçoit chacun des dix-neuf autres une
                fois, il suffit donc de retirer les rencontres déjà jouées.
              </li>
              <li>
                Chaque match restant reçoit ses deux <Tex>{'\\lambda'}</Tex> du modèle de buts, puis 10 000 scores sont tirés
                au sort.
              </li>
              <li>
                Chaque saison simulée est classée aux points, puis à la différence de buts, puis aux buts marqués, puis au
                tirage au sort.
              </li>
              <li>La probabilité d'un événement est la part des 10 000 saisons où il se produit.</li>
            </ol>
            <p>
              Le calcul est vectorisé avec des matrices d'incidence équipes × matchs : jusqu'à 3,8 millions de matchs tirés
              en un quart de seconde.
            </p>
          </section>

          <section id="trophees">
            <h2>Meilleur buteur et meilleur passeur</h2>
            <p>
              Même principe, au niveau des joueurs. Les buts qu'un club doit encore marquer suivent une loi de Poisson
              de moyenne <Tex>{'\\Lambda_{club}'}</Tex>, la somme de ses buts attendus sur les matchs restants. Chaque but
              revient à un joueur avec une probabilité égale à sa part, multipliée par <Tex>{'\\rho'}</Tex>, la proportion
              de buts attribués à un buteur la saison précédente, comme pour les buteurs d'un match.
            </p>
            <p>
              Une propriété de la loi de Poisson simplifie tout : répartir au hasard un nombre de buts poissonnien donne,
              pour chaque joueur, un nombre de buts lui aussi poissonnien et indépendant des autres. On tire donc
              directement le total futur de chaque joueur, sans simuler but par but :
            </p>
            <Tex display>{'\\text{Buts}_i^{\\text{fin}} = \\text{buts}_i^{\\text{actuels}} + \\text{Poisson}\\big(\\Lambda_{club} \\cdot \\rho \\cdot \\text{part}_i\\big)'}</Tex>
            <p>
              Pour les passes décisives, <Tex>{'\\rho'}</Tex> devient le nombre de passes par but, mesuré lui aussi sur la
              saison précédente (environ 0,66). Un joueur transféré garde ses buts marqués dans son ancien club, puisque le
              titre compte tous les buts en Premier League, mais n'est projeté que dans son club actuel. En cas d'égalité
              dans une saison simulée, le titre est partagé.
            </p>
            <p>
              La part de chaque joueur s'appuie sur sa saison précédente : après cinq journées, les 27 buts d'un attaquant
              l'an dernier en disent plus long que son poste. Les nouveaux venus en Premier League repartent de la moyenne
              de leur poste.
            </p>
          </section>

          <section id="validation">
            <h2>La validation</h2>
            <p>
              Aucun modèle n'est testé sur des matchs qu'il a déjà vus. Pour chaque saison de test, l'entraînement ne
              porte que sur les saisons précédentes. Un découpage aléatoire laisserait un modèle entraîné sur 2022
              « prédire » 2019, et tous les résultats seraient flatteurs.
            </p>
            <p>
              Le critère principal est la log loss, complétée par le score de Brier. Les deux récompensent des
              probabilités bien calibrées et pénalisent l'excès de confiance, ce que le simple taux de bons pronostics ne
              voit pas.
            </p>
            <Tex display>{'\\text{Log loss} = -\\frac{1}{N}\\sum_{m=1}^{N} \\log P_m(\\text{résultat réel})'}</Tex>

            {rows.length > 0 && (
              <figure className="table-figure">
                <div className="table-scroll">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Modèle</th>
                        <th className="num">Bons pronostics</th>
                        <th className="num">Log loss</th>
                        <th className="num">Brier</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((r) => (
                        <tr key={r.model} className={r === best ? 'is-best' : r.model === 'naive_base_rate' ? 'is-reference' : ''}>
                          <td>{MODEL_NAMES[r.model] ?? r.model}</td>
                          <td className="num tabular">{pct(parseFloat(r.accuracy))}</td>
                          <td className="num tabular">{parseFloat(r.log_loss).toFixed(4).replace('.', ',')}</td>
                          <td className="num tabular">{parseFloat(r.brier_score).toFixed(4).replace('.', ',')}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <figcaption className="footnote">
                  {int(parseInt(best.n_matches))} matchs, {best.n_seasons} saisons de test depuis 2013-14. Plus la log loss et
                  le Brier sont bas, meilleur est le modèle.
                </figcaption>
              </figure>
            )}
            {best && reference && (
              <p>
                Tous les modèles font nettement mieux que la référence, qui prédit toujours les fréquences historiques (log
                loss {num2(parseFloat(reference.log_loss))}). Un peu plus d'un bon pronostic sur deux paraît modeste, mais un
                match de football reste très aléatoire : même en connaissant exactement la force des équipes, nuls et
                surprises restent fréquents.
              </p>
            )}
          </section>

          <section id="bilan">
            <h2>Le bilan de la saison</h2>
            <p>
              La page Bilan applique la même règle à la saison en cours, journée par journée. Avant chaque journée, tout
              est reconstruit avec les seules données disponibles à ce moment-là : les modèles sont réentraînés sur les
              matchs précédents, et les statistiques des joueurs sont recalculées à partir des feuilles de match
              antérieures. Les totaux de saison actuels contiennent déjà les buts qu'on cherche à prédire, ils ne sont
              donc jamais utilisés ici.
            </p>
            <p>
              Chaque indicateur est comparé à ce que nos propres probabilités annonçaient. Si le favori est donné à 55 %
              en moyenne, un modèle bien calibré a raison environ 55 % du temps. Le nombre de bons pronostics suit alors
              une loi dont on connaît la moyenne et l'écart-type :
            </p>
            <Tex display>{'\\mathbb{E}[\\text{réussites}] = \\sum_m p_m, \\qquad \\sigma^2 = \\sum_m p_m (1 - p_m)'}</Tex>
            <p>
              La fourchette affichée (moyenne ± 1,28 σ) contient le vrai nombre 8 fois sur 10 si le modèle dit vrai.
              Sortir de la bande de temps en temps est normal ; en sortir durablement signalerait un modèle trop sûr de
              lui, ou pas assez. Le bilan est recalculé avec le modèle actuel : il mesure le modèle d'aujourd'hui, pas un
              historique de ce que le site affichait à l'époque.
            </p>
          </section>

          <section id="limites">
            <h2>Les limites</h2>
            <ul className="limits">
              <li>
                La force des équipes est figée pendant la simulation. Blessures, transferts et changements d'entraîneur ne
                sont pas modélisés, et l'incertitude sur la force elle-même n'est pas propagée : le favori paraît un peu
                trop sûr de lui, surtout en début de saison.
              </li>
              <li>
                Les compositions d'équipe ne sont pas connues. Les buteurs probables supposent un temps de jeu habituel ;
                un titulaire blessé reste dans la liste. Sur les cinq premières journées de 2026-27, 12 % des joueurs listés
                n'ont pas joué le match, et c'est la principale raison pour laquelle ils marquent un peu moins que prévu.
              </li>
              <li>
                Le modèle de buts traite les deux équipes comme indépendantes, ce qui sous-estime légèrement les petits
                scores nuls (0-0, 1-1).
              </li>
              <li>Un transfert n'apparaît qu'une fois répercuté par FBref, au rafraîchissement hebdomadaire suivant.</li>
            </ul>
          </section>
        </article>
      </div>
    </div>
  )
}

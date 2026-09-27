import type { BacktestRow, Meta } from '../api'
import { Tex } from '../components/Tex'
import { int, longDate, num2, pct } from '../format'

const MODEL_NAMES: Record<string, string> = {
  elo_logistic: 'Elo + régression logistique',
  baseline_logistic: 'Régression logistique (forme, classement, Elo)',
  random_forest: 'Random Forest',
  xgboost: 'XGBoost',
  poisson: 'Poisson (modèle de buts)',
  naive_base_rate: 'Baseline naïve (fréquences historiques)',
}

const SECTIONS = [
  ['vue', "Vue d'ensemble"],
  ['donnees', 'Les données'],
  ['elo', 'Le rating Elo'],
  ['poisson', 'Le modèle de buts'],
  ['buteurs', 'Les buteurs probables'],
  ['simulation', 'La simulation de saison'],
  ['validation', 'Est-ce que ça marche ?'],
  ['limites', 'Les limites'],
] as const

const PIPELINE = [
  { n: '1', title: 'Données', text: 'Résultats depuis 2000, effectifs de la saison' },
  { n: '2', title: 'Notes', text: 'Elo de chaque club, attaque et défense' },
  { n: '3', title: 'Modèles', text: 'Issue du match, score exact, buteurs' },
  { n: '4', title: 'Simulation', text: '10 000 saisons rejouées' },
  { n: '5', title: 'Validation', text: 'Testé sur des saisons jamais vues' },
]

export function HowItWorksPage({ meta, backtest }: { meta: Meta | null; backtest: BacktestRow[] }) {
  const rows = [...backtest].sort((a, b) => parseFloat(a.log_loss) - parseFloat(b.log_loss))
  const best = rows[0]
  const naive = rows.find((r) => r.model === 'naive_base_rate')

  return (
    <div className="page page-doc">
      <header className="page-header">
        <span className="eyebrow">Méthode</span>
        <h1>Comment ça marche</h1>
        <p className="lede">
          De 25 ans de résultats à une probabilité pour chaque match, chaque score, chaque buteur et chaque place au
          classement, avec la façon dont on vérifie que ces probabilités valent quelque chose.
        </p>
      </header>

      <div className="doc-layout">
        <nav className="doc-toc" aria-label="Sommaire">
          <span className="eyebrow">Sommaire</span>
          <ol>
            {SECTIONS.map(([id, label]) => (
              <li key={id}>
                <a href={`#/methode/${id}`} onClick={(e) => (e.preventDefault(), document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' }))}>
                  {label}
                </a>
              </li>
            ))}
          </ol>
        </nav>

        <article className="doc">
          <section id="vue">
            <h2>Vue d'ensemble</h2>
            <ol className="pipeline">
              {PIPELINE.map((s) => (
                <li key={s.n} className="pipeline-step">
                  <span className="pipeline-n">{s.n}</span>
                  <strong>{s.title}</strong>
                  <span>{s.text}</span>
                </li>
              ))}
            </ol>
            <p>
              L'idée centrale : un pronostic comme « Arsenal gagne » est bien moins utile que « Arsenal 51 %, nul 25 %,
              Liverpool 24 % ». Tout le projet produit donc des <em>probabilités</em>, et c'est leur qualité que l'on
              mesure, pas seulement le nombre de bons pronostics.
            </p>
          </section>

          <section id="donnees">
            <h2>Les données</h2>
            <p>
              <strong>Résultats des matchs</strong> :{' '}
              <a href="https://www.football-data.co.uk/englandm.php">football-data.co.uk</a>, un fichier par saison
              {meta && (
                <>
                  , soit <strong>{int(meta.n_matches_history)} matchs</strong> de {meta.first_season} à aujourd'hui.
                  Dernier match pris en compte : <strong>{longDate(meta.last_match_date)}</strong>
                </>
              )}
              .
            </p>
            <p>
              <strong>Effectifs et buts des joueurs</strong> : <a href="https://fbref.com/">FBref</a>, via la librairie{' '}
              <code>soccerdata</code>
              {meta?.players_snapshot_date && <> (instantané du {longDate(meta.players_snapshot_date)})</>}. Les 20 équipes
              proposées sont celles de la saison en cours, déduites automatiquement de la date du jour.
            </p>
            <p>
              Une tâche automatique met à jour le dépôt chaque mercredi soir : nouveaux résultats, nouveaux effectifs,
              nouveau backtest.
            </p>
          </section>

          <section id="elo">
            <h2>Le rating Elo</h2>
            <p>
              Chaque club a une note, 1 500 au départ. Avant un match, la note donne un score attendu pour l'équipe à
              domicile, avantage du terrain compris (<Tex>{'H = 60'}</Tex> points) :
            </p>
            <Tex display>{'E_{dom} = \\frac{1}{1 + 10^{-(R_{dom} + H - R_{ext})/400}}'}</Tex>
            <p>
              Après le match, les notes bougent selon l'écart entre le résultat réel <Tex>{'S'}</Tex> (1, ½ ou 0) et
              ce score attendu. Une large victoire compte plus qu'une courte, via un multiplicateur de marge{' '}
              <Tex>{'M'}</Tex> :
            </p>
            <Tex display>{"R'_{dom} = R_{dom} + K \\cdot M \\cdot (S - E_{dom}), \\qquad K = 20"}</Tex>
            <p>
              Pour transformer un écart de notes en probabilités de victoire, de nul et de défaite, on ajuste une
              régression logistique multinomiale sur 25 ans de matchs. C'est ce modèle qui donne les trois pourcentages
              en tête de la page Match.
            </p>
            <Tex display>{'P(Y = k) = \\frac{e^{\\beta_{k0} + \\beta_{k1}\\,\\Delta\\text{Elo}}}{\\sum_j e^{\\beta_{j0} + \\beta_{j1}\\,\\Delta\\text{Elo}}}, \\quad k \\in \\{\\text{dom}, \\text{nul}, \\text{ext}\\}'}</Tex>
          </section>

          <section id="poisson">
            <h2>Le modèle de buts (Poisson)</h2>
            <p>
              Pour prédire un score exact, on modélise les buts de chaque équipe comme une loi de Poisson, dont la
              moyenne dépend de l'attaque de l'une et de la défense de l'autre :
            </p>
            <Tex display>{'\\text{Buts}_{dom} \\sim \\text{Poisson}(\\lambda_{dom}), \\quad \\log \\lambda_{dom} = \\mu + \\text{avantage} + \\text{attaque}_{dom} - \\text{défense}_{ext}'}</Tex>
            <p>La probabilité d'un score exact est alors le produit des deux lois :</p>
            <Tex display>{'P(i\\text{–}j) = \\frac{\\lambda_{dom}^{\\,i} e^{-\\lambda_{dom}}}{i!} \\cdot \\frac{\\lambda_{ext}^{\\,j} e^{-\\lambda_{ext}}}{j!}'}</Tex>
            <p>Deux réglages font toute la différence, et tous deux ont été choisis sur des saisons de validation (2008-2012) antérieures aux saisons de test :</p>
            <ul>
              <li>
                <strong>Le passé s'efface.</strong> Un match compte deux fois moins tous les 365 jours :{' '}
                <Tex>{'w = 0{,}5^{\\,\\text{âge}/365}'}</Tex>. Sans ça, un club promu serait jugé sur sa dernière
                saison en Premier League, parfois vieille de 25 ans.
              </li>
              <li>
                <strong>Prudence avec les petits échantillons.</strong> Une pénalité L2 ramène chaque équipe vers la
                moyenne de la ligue tant qu'on a peu de matchs récents sur elle.
              </li>
            </ul>
            <div className="lesson">
              <span className="eyebrow">Leçon apprise en chemin</span>
              <p>
                Une première version projetait un promu à 21 points après un mauvais mois : 5 matchs suffisaient à
                écraser tout le reste. Le coupable était un backtest qui n'évaluait le modèle qu'<em>avant</em> chaque
                saison, jamais en cours de saison comme sur ce site. En le réévaluant avec un réentraînement chaque
                semaine, la bonne régularisation s'est imposée : la log loss sur les matchs de début de saison est
                passée de 0,999 à 0,980.
              </p>
            </div>
          </section>

          <section id="buteurs">
            <h2>Les buteurs probables</h2>
            <p>
              Plutôt qu'un modèle par joueur (la plupart marquent trop peu pour être estimés seuls), on répartit les
              buts attendus de l'équipe entre ses joueurs. La part de chacun mélange ses buts de la saison et un a
              priori fondé sur son poste et son temps de jeu, avec <Tex>{'K = 8'}</Tex> buts fictifs :
            </p>
            <Tex display>{'\\text{part}_i = \\frac{\\text{buts}_i + K \\cdot \\text{a priori}_i}{\\text{buts}_{équipe} + K}'}</Tex>
            <p>
              En début de saison, l'a priori pèse lourd : 4 buts en 5 matchs ne donnent pas 60 % de l'attaque à un
              seul joueur. À mi-saison, les vrais buts dominent. La part est ensuite ajustée par la forme récente
              (bornée entre ×0,5 et ×1,8), puis :
            </p>
            <Tex display>{'\\lambda_i = \\lambda_{équipe} \\cdot \\text{part}_i, \\qquad P(\\text{marque}) = 1 - e^{-\\lambda_i}'}</Tex>
          </section>

          <section id="simulation">
            <h2>La simulation de saison</h2>
            <ol className="steps">
              <li>
                <strong>Le classement réel</strong> est calculé à partir des matchs déjà joués.
              </li>
              <li>
                <strong>Les matchs restants</strong> se déduisent sans calendrier externe : chaque club reçoit chacun
                des 19 autres une fois, donc restant = tous les couples − ceux déjà joués.
              </li>
              <li>
                <strong>Chaque match restant</strong> reçoit ses deux <Tex>{'\\lambda'}</Tex> du modèle Poisson, et
                on tire au hasard 10 000 scores par match.
              </li>
              <li>
                <strong>Chaque saison simulée</strong> est classée : points, puis différence de buts, puis buts
                marqués, puis tirage au sort.
              </li>
              <li>
                <strong>La probabilité</strong> d'un événement est la part des 10 000 saisons où il se produit.
              </li>
            </ol>
            <p>
              Le calcul est entièrement vectorisé (matrices d'incidence équipes × matchs) : 10 000 saisons, soit
              jusqu'à 3,8 millions de matchs tirés au sort, tournent en un quart de seconde.
            </p>
          </section>

          <section id="validation">
            <h2>Est-ce que ça marche ?</h2>
            <p>
              On ne teste jamais un modèle sur des matchs qu'il a vus. Pour chaque saison de test, le modèle est
              entraîné uniquement sur les saisons précédentes (<em>walk-forward</em>). Un découpage aléatoire laisserait
              un modèle entraîné sur 2022 « prédire » 2019, et tous les modèles paraîtraient meilleurs qu'ils ne le sont.
            </p>
            <p>
              On mesure surtout la <strong>log loss</strong> et le <strong>score de Brier</strong>, qui récompensent
              des probabilités bien calibrées et punissent la confiance mal placée, plus que le simple taux de bons
              pronostics :
            </p>
            <Tex display>{'\\text{Log loss} = -\\frac{1}{N}\\sum_{m=1}^{N} \\log P_m(\\text{résultat réel})'}</Tex>

            {rows.length > 0 && (
              <div className="table-scroll">
                <table className="doc-table">
                  <thead>
                    <tr>
                      <th>Modèle</th>
                      <th className="num">Bons pronostics</th>
                      <th className="num">Log loss ↓</th>
                      <th className="num">Brier ↓</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r) => (
                      <tr key={r.model} className={r === best ? 'is-best' : r.model === 'naive_base_rate' ? 'is-baseline' : ''}>
                        <td>{MODEL_NAMES[r.model] ?? r.model}</td>
                        <td className="num tabular">{pct(parseFloat(r.accuracy))}</td>
                        <td className="num tabular">{parseFloat(r.log_loss).toFixed(4).replace('.', ',')}</td>
                        <td className="num tabular">{parseFloat(r.brier_score).toFixed(4).replace('.', ',')}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="table-note muted">
                  {int(parseInt(best.n_matches))} matchs sur {best.n_seasons} saisons de test, depuis 2013-14. ↓ = plus bas
                  est meilleur.
                </p>
              </div>
            )}
            {best && naive && (
              <p>
                Tous les modèles battent nettement la baseline naïve (log loss {num2(parseFloat(naive.log_loss))}), qui
                prédit toujours les fréquences historiques. Un peu plus d'un match sur deux bien pronostiqué peut
                sembler peu, mais le football est très aléatoire : même en connaissant parfaitement la force des
                équipes, un nul ou une surprise restent fréquents.
              </p>
            )}
          </section>

          <section id="limites">
            <h2>Les limites</h2>
            <ul className="limits">
              <li>
                <strong>Forces figées pendant la simulation.</strong> Blessures, transferts et changements
                d'entraîneur ne sont pas modélisés, et l'incertitude sur la force des équipes n'est pas propagée : le
                favori paraît un peu trop sûr de son fait, surtout en début de saison.
              </li>
              <li>
                <strong>Pas de compositions d'équipe.</strong> Les buteurs probables supposent un temps de jeu
                habituel. Un titulaire blessé reste dans la liste.
              </li>
              <li>
                <strong>Buts indépendants.</strong> Le modèle Poisson traite les buts des deux équipes comme
                indépendants, ce qui sous-estime légèrement les petits scores nuls (0-0, 1-1).
              </li>
              <li>
                <strong>Des données, pas des nouvelles.</strong> Un transfert n'apparaît qu'une fois répercuté par
                FBref, au rafraîchissement hebdomadaire suivant.
              </li>
            </ul>
          </section>
        </article>
      </div>
    </div>
  )
}

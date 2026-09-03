const SRC_T = "(Zdroj: vlastní zpracování autora v jazyce Python, knihovna Matplotlib; programový kód byl vytvořen s využitím jazykového modelu Claude, Opus 4.8, Anthropic; ilustrativní syntetická data.)";
const SRC_R = "(Zdroj: vlastní zpracování autora v jazyce Python, knihovna Matplotlib, na datech vlastního backtestu; programový kód byl vytvořen s využitím jazykového modelu Claude, Opus 4.8, Anthropic.)";
const FV = "docs/figures_vysledky/";
const FT = "docs/figures_teorie/";

module.exports = [
// ---------- TITULNÍ BLOK ----------
["titlepage", "Replikace a ověření robustnosti VWAP trendové obchodní strategie na futures kontraktu NQ"],
["subtitle", "Replication and Robustness Assessment of a VWAP Trend-Following Trading Strategy on the NQ Futures Contract"],
["author", "Seminární práce"],
["author", "Gymnázium Teplice, Čs. dobrovolců 11"],
["author", "Autor: Jan Klimša   •   Konzultant: R. Gramskopf, Ph.D.   •   2026"],
["author", "**VZOR / INSPIRACE — určeno k vlastnímu přepsání, ne k doslovnému převzetí.**"],
["pagebreak"],

// ---------- ANOTACE ----------
["h1", "Anotace"],
["p", "Práce replikuje VWAP trendovou obchodní strategii popsanou Zarattinim a Azizem (1) a posuzuje, zda si její historická výkonnost udrží kvalitu po přenosu na futures kontrakt NQ, po započtení realistických transakčních nákladů a po sérii testů robustnosti. Strategie byla nezávisle naprogramována a otestována backtestingem na minutových datech platformy QuantConnect. Původní výsledky na QQQ se podařilo replikovat, po přechodu na realistické náklady a jiné instrumenty se však ukázalo, že výhoda je silně závislá na konkrétním trhu i na výši nákladů. Finální konfigurace pro NQ s hysterezním pásmem a dvěma denními filtry dosáhla na vývojových datech příznivých ukazatelů, jednorázová validace na neviděných datech ovšem vyšla nejednoznačně. Práce proto formuluje závěry opatrně a dokumentuje i slepé uličky."],
["p", "**Klíčová slova:** VWAP, trend following, backtesting, přeučení, robustnost, futures NQ, transakční náklady, Monte Carlo, bootstrap, hypotéza efektivních trhů"],

["h1", "Annotation"],
["p", "This thesis replicates the VWAP trend-following strategy described by Zarattini and Aziz (1) and assesses whether its historical performance survives transfer to the NQ futures contract, the inclusion of realistic transaction costs, and a battery of robustness tests. The strategy was independently coded and backtested on one-minute data from the QuantConnect platform. The original QQQ results were reproduced, but once realistic costs and other instruments were introduced, the edge proved highly dependent on the specific market and cost level. The final NQ configuration, using a hysteresis band and two daily filters, achieved favourable in-sample metrics, yet a single out-of-sample validation was inconclusive. The conclusions are therefore stated cautiously, and dead ends are documented as well."],
["p", "**Keywords:** VWAP, trend following, backtesting, overfitting, robustness, NQ futures, transaction costs, Monte Carlo, bootstrap, efficient market hypothesis"],
["pagebreak"],

// ---------- ÚVOD ----------
["h1", "Úvod"],
["p", "Retailové obchodování na finančních trzích má jeden trvalý problém: strategií, které slibují vysoké a stabilní výnosy, jsou doslova mraky, ale málokterá z nich obstojí, když ji člověk podrobí pořádnému ověření (2). Většina se opírá o efektně vypadající graf historické výkonnosti. A přitom právě zde leží to, na čem obchodníkovi nejvíc záleží: rozdíl mezi strategií, která na minulých datech jen vypadala výdělečně, a takovou, jejíž výhoda je skutečná a přenositelná jinam. Tomuto rozdílu se práce věnuje."],
["p", "Jako předmět zkoumání jsem si vybral odbornou studii Zarattiniho a Azize (1), která popisuje strategii postavenou na indikátoru VWAP a uvádí u ní roční zhodnocení přes čtyřicet procent při velmi příznivém poměru výnosu k riziku. U tak silného tvrzení se nabízí otázka, jestli jde o jev, který se na trhu spolehlivě opakuje, nebo o číslo, které drží jen díky jednomu nástroji, jednomu období a několika zjednodušujícím předpokladům."],
["p", "Prověřit se to dá replikací a následnými testy robustnosti. Replikace znamená naprogramovat pravidla nezávisle a zjistit, zda vedou ke stejnému výsledku. Testy robustnosti jdou dál a ptají se, zda výhoda vydrží i mimo původní podmínky: na jiných nástrojích, po započtení reálných nákladů a na datech, která při vývoji ještě neexistovala. Zároveň jsou obranou proti nejzrádnějšímu úskalí kvantitativního výzkumu, přeučení (overfitting)."],
["p", "**Cílem práce** je replikovat výsledky VWAP trendové strategie Zarattiniho a Azize (1) a posoudit, zda její historická výkonnost obstojí i po přenosu na futures kontrakt NQ, tedy po započtení realistických nákladů a po testech robustnosti. Odtud vedou tři **výzkumné otázky:** Do jaké míry se dají původní výsledky zopakovat na datech QQQ a TQQQ? Co s výsledky udělá přenos na jiné instrumenty a zahrnutí nákladů? A jsou pozitivní výsledky upravené strategie stabilní v čase, na sousedních hodnotách parametrů i na datech, která se na jejím vývoji nepodílela?"],
["p", "Metodicky jde o kvantitativní replikační a simulační studii. Nejprve vymezím pojmy, pak popíšu data a metodologii. Následuje vlastní replikace, přenos a úprava strategie na futures NQ a nakonec testy robustnosti spolu s validací na neviděných datech a shrnutím limitů. Závěr odpovídá na výzkumné otázky."],
["p", "**Poznámka k využití nástrojů.** Při práci jsem využil jazykový model umělé inteligence (Claude, Opus 4.8, Anthropic) jako pomůcku pro generování a ladění programového kódu (Python, Pine Script) a jako výpočetního asistenta. Návrh výzkumu, volbu testů, interpretaci výsledků i text práce jsem zpracoval samostatně; rozsah využití modelu uvádím transparentně a je vyznačen i u obrázků, jejichž kód takto vznikl."],
["pagebreak"],

// ---------- 1 TEORIE ----------
["h1", "1  Teoretická a odborná východiska"],
["p", "Tato kapitola vymezuje pojmy, o které se práce opírá. Začnu indikátorem VWAP a jeho rolí ve vnitrodenním obchodování, přejdu k principu strategií sledujících trend a oba přístupy zasadím do sporu o efektivnosti trhů. Kapitolu uzavřu backtestingem a jeho největší slabinou, přeučením."],

["h2", "1.1  VWAP a jeho role ve vnitrodenním obchodování"],
["p", "VWAP (Volume-Weighted Average Price, cenový průměr vážený objemem) udává průměrnou cenu nástroje za dané období, když se jednotlivé ceny zváží podle zobchodovaného objemu. Od obyčejného klouzavého průměru se liší tím, že přikládá větší váhu hladinám, kde proteklo víc kontraktů. Ve vnitrodenní podobě se počítá pro každou seanci zvlášť a na jejím začátku se resetuje."],
["p", "Původně vznikl k hodnocení kvality provedení obchodu: institucionální investoři srovnávali dosaženou průměrnou cenu s VWAPem, a když nakoupili pod ním, obchodovali výhodně (3). Z tohoto srovnávacího použití se časem stal i orientační bod pro rozhodování, protože VWAP představuje jakousi „férovou“ vnitrodenní cenu. V praxi se s ním pracuje dvěma opačnými způsoby: jedni sázejí na návrat ceny k VWAP (mean reversion), druzí sledují, na které straně VWAP se cena drží, a berou to jako signál převažujícího směru. Právě z druhého přístupu vychází strategie zkoumaná v této práci. Sám indikátor je jen referenční hladina; obchodní systém z něj udělají teprve pravidla vstupu a výstupu."],
["placeholder", "[[ SEM VLOŽ VLASTNÍ SCREENSHOT VWAP Z TRADINGVIEW ]]"],
["caption", "Obrázek 1 – Ukázka indikátoru VWAP na minutovém grafu kontraktu NQ; bílá křivka je průběžně počítaný session VWAP. (Zdroj: vlastní zpracování v platformě TradingView.)"],

["h2", "1.2  Trend following jako obchodní přístup"],
["p", "Sledování trendu (trend following) sází na to, že rozjetý cenový pohyb bude spíš pokračovat než se otočit. Blízko k tomu má jev zvaný momentum, tedy sklon nástrojů, které v nedávné době rostly, růst dál, a naopak (4). Momentum se nepotvrdilo jen napříč akciemi, ale i v čase u jednotlivých nástrojů (5), takže patří k nejrobustnějším empirickým jevům moderních financí."],
["p", "Strategie sledující trend charakterizuje nesouměrné rozdělení výsledků: úspěšnost bývá nízká a většina obchodů skončí malou ztrátou, zisk ale přinese menšina povedených obchodů, která ztráty s přehledem vyrovná. Výdělečnost tedy nestojí na tom, jak často má obchodník pravdu, ale na poměru mezi průměrnou výhrou a průměrnou ztrátou. Na tuto vlastnost je třeba myslet už teď, protože bude zásadní při výkladu výsledků: vysoká úspěšnost sama o sobě není důkazem výdělečnosti."],
["p", "Opakem je návrat k průměru (mean reversion), který počítá s korekcí přehnaných pohybů. Oba přístupy dokážou vydělávat i prodělávat podle tržního režimu: klidným trhům svědčí návrat k průměru, trhům s výrazným směrovým pohybem sledování trendu. Tato závislost na režimu je jeden z důvodů, proč později testuji stabilitu strategie v čase."],

["h2", "1.3  Hypotéza efektivních trhů a její kritika"],
["p", "Zda vůbec může technická strategie systematicky vydělávat, řeší hypotéza efektivních trhů (Efficient Market Hypothesis). Fama (6) tvrdí, že trh zpracovává dostupné informace natolik dobře, že je ceny v každém okamžiku plně obsahují, a rozlišuje tři formy efektivnosti: slabou (ceny nesou veškerou informaci z minulého vývoje), polosilnou (i veřejně dostupné informace) a silnou (i neveřejné). Už slabá forma znamená, že strategie postavené výhradně na historii ceny, tedy i technická analýza a sledování trendu, by dlouhodobě neměly vydělávat nadprůměrně."],
["p", "Hypotéza si od začátku vysloužila kritiku. Grossman a Stiglitz (7) poukázali na vnitřní rozpor dokonale efektivního trhu: kdyby ceny okamžitě odrážely úplně vše, nikdo by neměl důvod si informace nákladně obstarávat, a efektivnost by se sama rozbila. K tomu praxe opakovaně naráží na anomálie, mezi které patří i momentum. Určitý most staví hypotéza adaptivních trhů Andrewa Loa (8): efektivnost není pevný stav, ale výsledek soupeření účastníků, kteří se učí a přizpůsobují. Obchodní výhody proto vznikat mohou, ale časem slábnou, jakmile je objeví a začne využívat dost obchodníků (crowding). Pro tuto práci je to trefné: pokud publikovaná strategie skutečně nějakou výhodu měla, dá se čekat, že po zveřejnění postupně vyprchává."],

["h2", "1.4  Backtesting a riziko přeučení"],
["p", "Backtesting spočívá v tom, že se pravidla strategie pustí na historická data a odhadne se, jak by se v minulosti chovala. Výhoda je zřejmá: hypotézy lze ověřit bez finančního rizika. Háček je v tom, že dobrý výsledek na minulých datech nic negarantuje o budoucnu. Spolehlivost navíc podkopává řada systematických chyb, například pohled do budoucnosti (look-ahead bias), zkreslení přežití (survivorship bias) a zvlášť podceněné transakční náklady, které z výnosné strategie klidně udělají ztrátovou."],
["p", "Nejzrádnější je ovšem přeučení (overfitting). Nastává, když se strategie, ať už vědomým laděním parametrů, nebo nevědomky opakovaným testováním, přizpůsobí náhodnému šumu jednoho vzorku místo skutečné zákonitosti. Bailey a kol. (9) ukazují, že stačí vyzkoušet dost variant a některá bude na minulých datech vypadat skvěle čistě náhodou. Čím víc konfigurací člověk protočí, tím pravděpodobněji narazí na falešně pozitivní nález; na problém mnohonásobného testování upozorňují Harvey, Liu a Zhu (10)."],
["p", "Aby šlo strategii se skutečnou výhodou odlišit od té, která uspěla jen náhodou, používá se několik vzájemně se doplňujících postupů. Základem je rozdělit historii na vývojovou (in-sample), kde se strategie navrhuje a ladí, a ověřovací (out-of-sample), která se odloží a otestuje se až nakonec, jednou jedinkrát (11). Rozšířením je walk-forward analýza, kde se okno vývoje a ověření posouvá historií (11)."],
["img", FT + "1_is_oos.png", "Obrázek 2 – Rozdělení dostupné historie na in-sample a out-of-sample část. " + SRC_T],
["p", "Bootstrap je statistická metoda, která odhaduje rozdělení veličiny opakovaným náhodným výběrem z dat s vracením (12). Z původní množiny výnosů se tisíckrát losuje nová umělá řada stejné délky a pro každou se dopočítá ukazatel, například celkový výnos, Sharpe ratio (13) nebo maximální drawdown. Z tisíců hodnot vznikne empirické rozdělení, z něhož lze odečíst medián, pásma spolehlivosti i pravděpodobnost kladného výsledku. Bootstrap tak jedno číslo promění v rozpětí možných výsledků. Předpokládá ovšem nezávislost výnosů; při silné autokorelaci je nutná opatrnost (14)."],
["img", FT + "7_bootstrap.png", "Obrázek 3 – Bootstrap: rozdělení odhadované statistiky získané z 5 000 výběrů s vracením; černě medián, červeně pásmo 5.–95. percentilu. " + SRC_T],
["p", "Monte Carlo simulace je širší třída metod, které rozdělení možných výsledků zkoumají přes velké množství náhodně generovaných scénářů (15). U obchodních strategií z jediné historické řady vznikne skupina alternativních průběhů zhodnocení. Zobrazuje se to buď jako svazek křivek (fan chart), nebo jako oblak bodů v prostoru výnos–riziko."],
["img", FT + "2_mc_fan.png", "Obrázek 4 – Monte Carlo jako svazek možných průběhů zhodnocení (fan chart); přerušovaná čára značí medián. " + SRC_T],
["img", FT + "3_mc_oblak.png", "Obrázek 5 – Monte Carlo jako oblak výsledků; každý bod je jeden scénář v prostoru výnos–maximální drawdown. " + SRC_T],
["p", "Bootstrap je vlastně jedním provedením Monte Carla, kde je zdrojem náhody přímo pozorovaný výnos. Robustnost se prověřuje i doplňkově, například rozkladem výsledků po jednotlivých letech nebo mapami parametrů."],
["img", FT + "4_vynosy_roky.png", "Obrázek 6 – Rozklad výnosů podle jednotlivých let; slouží k posouzení, zda výhoda přetrvává v čase. " + SRC_T],
["p", "Mapy parametrů ukazují, zda dobré výsledky tvoří souvislou plochu, nebo jen osamocený vrchol, což je typický příznak přeučení. Vše dohromady stojí na jednoduchém poznatku: jedno příznivé číslo z backtestu nestačí, teprve odhad jeho nejistoty a stability rozhodne, zda je strategie robustní (16; 17)."],
["img", FT + "5_heatmapa_overfit_robust.png", "Obrázek 7 – Mapa parametrů: vlevo přeučená strategie s izolovaným vrcholem, vpravo robustní strategie se širokou plošinou. " + SRC_T],
["pagebreak"],

// ---------- 2 METODOLOGIE ----------
["h1", "2  Data a metodologie"],
["h2", "2.1  Typ výzkumu a celkový postup"],
["p", "Práci jsem pojal jako kvantitativní replikační a simulační studii postavenou na backtestingu. Postupoval jsem v pěti navazujících krocích: nezávislá replikace pravidel, přenos na další instrumenty s realistickými náklady, úprava pro futures NQ, testy robustnosti a nakonec jednorázová validace na neviděných datech. Pořadí není náhodné, každý krok je přísnější než předchozí a má odhalit, zda výhoda strategie přežije zpřísnění podmínek."],
["h2", "2.2  Datové zdroje a nástroje"],
["p", "Historická data i výpočetní zázemí pocházejí z platformy QuantConnect, přesněji z jejího enginu LEAN (18). Pracoval jsem s minutovými daty, protože strategie je vnitrodenní. Statistické analýzy a grafy jsem zpracoval v jazyce Python (pandas, NumPy, SciPy, Matplotlib) a výsledný indikátor pro živé sledování trhu napsal v jazyce Pine Script na platformě TradingView (19). Při programování jsem využil jazykový model Claude (Opus 4.8, Anthropic) jako pomůcku pro generování a ladění kódu; návrh a interpretace jsou moje vlastní."],
["h2", "2.3  Instrumenty a časové období"],
["p", "Replikaci jsem provedl na fondu QQQ a jeho trojnásobně pákové variantě TQQQ. Kvůli přenosu strategie jsem přibral ETF SPY a futures kontrakty ES a NQ; těžištěm se nakonec stal NQ. Vývojové období (in-sample) sahá od roku 2018 do září 2025. Okno od října 2025 jsem hned na začátku fyzicky oddělil a po celou dobu vývoje se ho nedotkl, protože slouží výhradně k závěrečné jednorázové validaci (out-of-sample)."],
["h2", "2.4  Konstrukce kontinuálního futures kontraktu"],
["p", "Futures kontrakty pravidelně expirují, takže souvislou historii je nutné poskládat navázáním jednotlivých expirací. Přechod (roll) se řídil podle otevřeného zájmu (open interest). Aby na spojích nevznikaly umělé cenové skoky, které by zkreslily výnosy, zarovnal jsem historii zpětně poměrovou metodou (backward ratio adjustment). Procentní změny cen tak zůstávají věrné, což je pro výpočet výnosů podstatnější než absolutní cenová hladina."],
["h2", "2.5  Pravidla obchodní strategie"],
["p", "Jádrem strategie je poloha ceny vůči session VWAP. Kolem VWAP jsem vymezil hysterezní pásmo široké 20 bazických bodů; do dlouhé pozice vstupuji, když se cena udrží nad horním okrajem, do krátké pod spodním. Pásmo brání překlápění pozice při drobném kmitání kolem průměru. Pravidla jsem zpřísnil do režimu „jeden obchod denně“ (reakce jen na první platný signál). Pozici zavírám při dotyku opačného okraje, nejpozději na konci dne v 16:00; žádná pozice nezůstává přes noc a strategie nepoužívá pevný ziskový cíl."],
["p", "Vstup jsem podmínil dvěma filtry odvozenými během vývoje:"],
["b", "**Filtr mezery (gap):** obchoduji jen ve dnech, kdy absolutní mezera mezi včerejším zavřením a dnešním otevřením překročí 25. percentil mezer za posledních 250 dní."],
["b", "**Filtr trendu:** vynechávám den po výrazně trendovém dni; trendovost měřím podílem |zavření − otevření| / (maximum − minimum), a pokud přesáhl 60. percentil za 250 dní, dnešek neobchoduji."],
["p", "Oba filtry pracují s klouzavými percentily z posledních 250 dní, takže se přizpůsobují trhu a nevyužívají informaci z budoucnosti."],
["h2", "2.6  Model transakčních nákladů a plnění"],
["p", "Protože podceněné náklady umějí z výdělečné strategie udělat ztrátovou, počítal jsem se dvěma scénáři: optimistickým 0,4 bazického bodu a konzervativním 1,2 bazického bodu na kompletní obchod (round-turn, vstup i výstup dohromady). Obě čísla zahrnují poplatek i skluz v plnění. Objednávky se v simulaci plní na otevírací ceně následující minutové svíčky. Velikost pozice odpovídá jednonásobku hodnoty účtu."],
["h2", "2.7  Rozdělení dat (in-sample / out-of-sample)"],
["p", "Základní obranou proti přeučení je oddělit vývojová a ověřovací data (11). Celý vývoj jsem prováděl na období 2018–2025. Ověřovací okno od října 2025 jsem otestoval až úplně nakonec, jednou jedinkrát; opakované testování by z něj udělalo další vývojová data a připravilo je o vypovídací hodnotu (17)."],
["h2", "2.8  Hodnoticí ukazatele a testy robustnosti"],
["p", "Výkonnost posuzuji čtyřmi ukazateli: složeným ročním výnosem (CAGR), poměrem výnosu k riziku (Sharpe ratio) (13), maximálním drawdownem a počtem obchodů s úspěšností (u úspěšnosti uvádím i interval spolehlivosti). Čísla z jednoho backtestu doplňuji rozkladem po letech, mapami parametrů a metodami bootstrap a Monte Carlo. Teprve shoda těchto testů rozhoduje, zda strategii pokládám za robustní."],
["pagebreak"],

// ---------- 3 REPLIKACE ----------
["h1", "3  Replikace původní studie"],
["h2", "3.1  Postup replikace na QQQ"],
["p", "Prvním krokem bylo ověřit, že dokážu nezávisle zreprodukovat výsledky Zarattiniho a Azize (1). Pravidla jsem naprogramoval od nuly podle popisu v jejich práci a spustil na fondu QQQ za období 2018–2023. Abych srovnával „jablka s jablky“, převzal jsem i jejich nákladový předpoklad (poplatek 0,0005 USD na akcii, nulový skluz). Realistické náklady přijdou až v následující kapitole; zde jde čistě o to, zda mi pravidla dají stejná čísla."],
["h2", "3.2  Výsledky a shoda s publikovanou studií"],
["table", [["metrika", "QQQ (moje)", "QQQ (studie)"], ["CAGR", "40,8 %", "43 %"], ["Sharpe", "2,01", "—"], ["max drawdown", "8,8 %", "9,4 %"], ["úspěšnost", "17,4 %", "~17 %"], ["poměr zisk/ztráta", "5,53", "~5"]]],
["p", "Výsledky se s původní prací shodují prakticky přesně; drobné rozdíly (43 % vs 40,8 %) padají do tolerance dané rozdílem datových zdrojů. Potvrzuje se i charakteristický profil trend-followingu z kapitoly 1: nízká úspěšnost kolem 17 %, kterou bohatě vyváží vysoký poměr zisku ke ztrátě (5,5). Replikaci na QQQ tedy pokládám za úspěšnou, pravidla jsou implementována správně."],
["h2", "3.3  Pákový nástroj TQQQ a jeho odchylka"],
["p", "U trojnásobně pákového TQQQ se shodovala celá struktura jednotlivých obchodů (úspěšnost 18,1 %, poměr zisk/ztráta 5,18, počet obchodů, drawdown 40,9 % vs 36,1 %), ale celkové složené zhodnocení zaostalo (CAGR 61,9 % vs uváděných 116 %). Rozdíl činí přibližně 0,7 bazického bodu na obchod a plně ho vysvětluje způsob, jakým poplatek za akcii dopadá na cenově upravená (split-adjusted) data v QuantConnectu oproti neupraveným cenám v původní studii. Nejde tedy o chybu v pravidlech, ale o datový artefakt, který se u často obchodovaného a několikrát štěpeného nástroje nasčítá. Tento krok potvrdil, že strategie je korektně implementovaná, a otevřel otázku pro zbytek práce: obstojí i po opuštění ideálního nákladového předpokladu?"],
["pagebreak"],

// ---------- 4 PŘENOS A ÚPRAVY ----------
["h1", "4  Přenos a úpravy strategie na futures NQ"],
["h2", "4.1  Přenos na SPY a ES: vliv transakčních nákladů"],
["p", "Jakmile jsem ideální nákladový předpoklad nahradil realistickým, obraz se zásadně změnil. Už na samotném QQQ spadl výsledek z hrubého zisku na net_opt +19,4 % (Sharpe 1,07) a při konzervativních nákladech dokonce na −14,0 %. Přenos na SPY a ES potvrdil, že jde o obecný problém: v hrubých číslech obě strategie zaostaly za prostým držením trhu (benchmark buy-and-hold +14,3 % ročně) a po započtení nákladů se propadly do ztráty."],
["table", [["instrument", "gross CAGR", "net_opt CAGR", "net_cons CAGR"], ["QQQ", "—", "+19,4 %", "−14,0 %"], ["SPY", "+9,8 %", "−8,0 %", "−35,5 %"], ["ES", "+12,0 %", "−6,1 %", "−34,1 %"]]],
["p", "Závěr je jednoznačný: strategie se na SPY a ES nepřenáší a její výhoda je specifická pro index Nasdaq-100 a mimořádně citlivá na náklady. To zúžilo pozornost na jediný slibný instrument, futures kontrakt NQ."],
["h2", "4.2  Hysterezní pásmo jako řešení nadměrného počtu obchodů"],
["p", "Základní pravidlo na NQ generovalo zhruba 16 obchodů denně. V hrubých číslech vypadalo skvěle (CAGR +36,1 %, Sharpe 1,88), ale po konzervativních nákladech spadlo na −17,8 %, protože náklady se násobí počtem obchodů. Řešením bylo hysterezní pásmo: rozšiřováním pásma klesá počet obchodů, a tím i celkové náklady. Při pásmu 20 bazických bodů se počet obchodů snížil o zhruba 85 % na přibližně 2,5 denně a konzervativní výsledek se dostal do kladných čísel (kolem +9,5 %), a to v obou polovinách vývojového období. Volba pásma přitom nestojí na osamoceném vrcholu, ale na souvislé ploše dobrých hodnot, jak ukazuje mapa parametrů."],
["img", FV + "overfitting_check.png", "Obrázek 8 – Kontrola přeučení: heatmapa pásmo × take-profit (in-sample celkový výnos). Zvolená konfigurace (pásmo 20 bps, bez pevného cíle) leží v souvislé ploše, ne na izolovaném vrcholu. Mřížka je počítána bez denních filtrů. " + SRC_R],
["h2", "4.3  Úprava do podoby „jeden obchod denně“ a denní filtry"],
["p", "Poslední úpravou byly dva denní filtry z podkapitoly 2.5. Filtr mezery vyřazuje klidné dny bez energie, filtr trendu vynechává den po silně trendovém dni. Zvlášť druhý filtr výrazně zkrotil riziko: maximální drawdown klesl z −15,7 % na −6,4 %, aniž by se rozbil výnos. Výsledná finální konfigurace pro NQ (session VWAP, pásmo 20 bps, jeden obchod denně, oba filtry) dosáhla na vývojových datech složeného ročního výnosu 10,5 %, Sharpe ratia 1,40 a maximálního drawdownu −6,4 %. Její robustnosti se věnuje následující kapitola."],
["pagebreak"],

// ---------- 5 ROBUSTNOST ----------
["h1", "5  Výsledky testů robustnosti"],
["p", "Finální konfiguraci jsem podrobil sérii testů z podkapitoly 2.8. Všechny níže uvedené výsledky jsou in-sample (2018 – září 2025) a slouží k posouzení stability, nikoli jako důkaz budoucí výdělečnosti."],
["p", "Křivka zhodnocení roste vytrvale a bez dramatických propadů, což potvrzuje i podvodní graf drawdownu s maximálním poklesem −6,4 %."],
["img", FV + "equity_curve.png", "Obrázek 9 – Křivka zhodnocení finální konfigurace (in-sample, počáteční kapitál 100 000 USD, konzervativní náklady 1,2 bps). " + SRC_R],
["img", FV + "drawdown.png", "Obrázek 10 – Podvodní graf (drawdown) finální konfigurace; maximální pokles −6,4 %. " + SRC_R],
["p", "Rozklad po jednotlivých letech ukazuje kladný výnos ve všech osmi letech, včetně roku 2022, kdy širší trh výrazně klesal. To naznačuje, že výhoda nestojí na jediném příznivém období."],
["img", FV + "annual_returns.png", "Obrázek 11 – Výnos po jednotlivých letech; kladný ve všech osmi letech vývojového období. " + SRC_R],
["p", "Mapa parametrů (nyní měřená Sharpe ratiem) potvrzuje závěr z kapitoly 4: zvolená konfigurace leží na souvislé plošině dobrých hodnot, ne na izolovaném vrcholu."],
["img", FV + "robustness_heatmap.png", "Obrázek 12 – Robustnost: Sharpe ratio napříč mřížkou pásmo × take-profit; zvolená konfigurace (rámeček) na souvislé plošině. " + SRC_R],
["p", "Metody bootstrap a Monte Carlo převádějí jediný výsledek na rozdělení možných scénářů. Pozorovaný backtest leží uvnitř mračna i u mediánu svazku drah. Je ovšem třeba upozornit, že bootstrap předpokládá nezávislost denních výnosů, a tím podhodnocuje krajní scénáře; velmi nízkou pravděpodobnost ztráty proto beru jako ilustraci rozptylu, ne jako záruku."],
["img", FV + "monte_carlo.png", "Obrázek 13 – Monte Carlo (4 000 bootstrapů denních výnosů) v prostoru výnos–drawdown; hvězda značí pozorovaný backtest. " + SRC_R],
["img", FV + "monte_carlo_fan.png", "Obrázek 14 – Monte Carlo: svazek 500 drah zhodnocení s pásmem 5.–95. percentilu; červená je pozorovaný backtest. " + SRC_R],
["p", "In-sample obraz je tedy konzistentní: strategie je zisková napříč lety, stabilní na sousedních parametrech a její pozorovaný výsledek není extrémem simulovaného rozdělení."],

["h2", "5.1  Jednorázová validace na neviděných datech"],
["p", "Rozhodující test proběhl na ověřovacím okně od října 2025, kterého jsem se během vývoje nedotkl. Podle předem stanoveného protokolu jsem provedl jediný běh, bez jakéhokoli dolaďování. Výsledek vyšel nejednoznačně: hrubá výhoda odpovídala přibližně +3,4 % ročně, tedy výrazně méně než in-sample úroveň kolem +18 % ročně, a bootstrapová pravděpodobnost kladného výnosu na tomto úseku činila jen zhruba 45 %, což je na úrovni náhody. Výsledek navíc omezuje technický limit platformy, která pro kontinuální NQ pokryla jen 71 % ověřovacího okna. Ověřovací data se tímto jediným během považují za spotřebovaná; opakovaný test na nich by už neměl vypovídací hodnotu."],
["pagebreak"],

// ---------- 6 DISKUSE ----------
["h1", "6  Diskuse výsledků a limity práce"],
["p", "Výsledky dávají odpovědi na tři výzkumné otázky. Za prvé, původní studii se na QQQ podařilo replikovat prakticky přesně; rozdíl u pákového TQQQ jsem vysvětlil datovým artefaktem, nikoli chybou pravidel. Za druhé, přenos na jiné instrumenty a započtení realistických nákladů výsledky zásadně zhoršily: na SPY a ES se strategie propadla do ztráty a i na QQQ byla po konzervativních nákladech ztrátová. Výhoda je tedy silně vázaná na index Nasdaq-100 a mimořádně citlivá na náklady, což bylo hlavní motivací přechodu na levněji obchodovatelný futures NQ a zavedení hysterezního pásma."],
["p", "Za třetí, upravená konfigurace pro NQ je na vývojových datech výnosná a v řadě ohledů robustní: zisková ve všech letech, stabilní na sousedních parametrech a bez extrémního postavení v simulacích. Klíčový je ale výsledek jednorázové validace na neviděných datech, který vyšel nejednoznačně. To dobře odpovídá hypotéze adaptivních trhů (8): pokud strategie nějakou výhodu měla, mohla po zveřejnění a s během času slábnout."],
["p", "Práce má několik limitů. Finální konfigurace vznikla po desítkách testů na obdobných datech, takže i přes obranná opatření nelze riziko přeučení zcela vyloučit; právě proto byl závěrečný test jednorázový. Bootstrap a Monte Carlo předpokládají nezávislost výnosů a podhodnocují krajní scénáře. Ověřovací okno bylo krátké a navíc zkrácené limitem dat, takže jeho vypovídací hodnota je omezená. Výsledky rovněž nezahrnují všechny reálné tržní tření (proměnlivý skluz při nízké likviditě, dopady velkých pozic). Poctivým výstupem proto není potvrzení výdělečné strategie, ale zmapování hranice, za kterou domnělá výhoda přestává platit."],
["pagebreak"],

// ---------- ZÁVĚR ----------
["h1", "Závěr"],
["p", "Cílem práce bylo replikovat VWAP trendovou strategii Zarattiniho a Azize (1) a posoudit, zda si její historická výkonnost udrží kvalitu po přenosu na futures NQ, po započtení realistických nákladů a po testech robustnosti. Replikace na QQQ se zdařila a potvrdila, že pravidla byla implementována správně. Přenos na jiné instrumenty a realistické náklady ovšem ukázaly, že výhoda je specifická pro index Nasdaq-100 a silně citlivá na náklady."],
["p", "Úpravou pro NQ (hysterezní pásmo, jeden obchod denně, dva denní filtry) se podařilo najít konfiguraci, která je na vývojových datech výnosná a robustní: složený roční výnos 10,5 %, Sharpe ratio 1,40, maximální drawdown −6,4 % a kladný výsledek ve všech osmi letech. Jednorázová validace na neviděných datech ale vyšla nejednoznačně, na úrovni náhody."],
["p", "Nelze proto tvrdit, že jde o spolehlivě výdělečnou strategii. Backtest ukazuje, jak by strategie vycházela na historických datech, nikoli jak bude vydělávat v budoucnu. Podařilo se najít historicky slibnou konfiguraci, jejíž skutečnou platnost musí ověřit další nezávislá data nebo dlouhodobý paper trading. Hlavním přínosem práce je poctivé zmapování toho, kde a proč domnělá výhoda přestává platit, což je před nasazením reálného kapitálu cennější než efektně vypadající křivka zhodnocení."],
["pagebreak"],

// ---------- SEZNAM ZDROJŮ ----------
["h1", "Seznam použitých zdrojů"],
["refs", [
"ZARATTINI, Carlo; AZIZ, Andrew. VWAP: The Holy Grail for Day Trading Systems [online]. SSRN Working Paper No. 4631351, 2023, s. [doplň stranu] [cit. 2026-07-22]. Dostupné z: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4631351",
"ARONSON, David R. Evidence-Based Technical Analysis: Applying the Scientific Method and Statistical Inference to Trading Signals. Hoboken (NJ): John Wiley & Sons, 2007, s. [doplň stranu]. ISBN 978-0-470-00874-4. Dostupné z: https://books.google.com/books?isbn=9780470008744",
"BERKOWITZ, Stephen A.; LOGUE, Dennis E.; NOSER, Eugene A. The Total Cost of Transactions on the NYSE. The Journal of Finance. 1988, roč. 43, č. 1, s. 97–112. ISSN 0022-1082. Dostupné z: https://doi.org/10.1111/j.1540-6261.1988.tb02591.x",
"JEGADEESH, Narasimhan; TITMAN, Sheridan. Returns to Buying Winners and Selling Losers: Implications for Stock Market Efficiency. The Journal of Finance. 1993, roč. 48, č. 1, s. 65–91. ISSN 0022-1082. Dostupné z: https://doi.org/10.1111/j.1540-6261.1993.tb04702.x",
"MOSKOWITZ, Tobias J.; OOI, Yao Hua; PEDERSEN, Lasse Heje. Time Series Momentum. Journal of Financial Economics. 2012, roč. 104, č. 2, s. 228–250. ISSN 0304-405X. Dostupné z: https://doi.org/10.1016/j.jfineco.2011.11.003",
"FAMA, Eugene F. Efficient Capital Markets: A Review of Theory and Empirical Work. The Journal of Finance. 1970, roč. 25, č. 2, s. 383–417. ISSN 0022-1082. Dostupné z: https://doi.org/10.2307/2325486",
"GROSSMAN, Sanford J.; STIGLITZ, Joseph E. On the Impossibility of Informationally Efficient Markets. The American Economic Review. 1980, roč. 70, č. 3, s. 393–408. ISSN 0002-8282. Dostupné z: https://www.jstor.org/stable/1805228",
"LO, Andrew W. The Adaptive Markets Hypothesis. The Journal of Portfolio Management. 2004, roč. 30, č. 5, s. 15–29. ISSN 0095-4918. Dostupné z: https://doi.org/10.3905/jpm.2004.442611",
"BAILEY, David H.; BORWEIN, Jonathan M.; LÓPEZ DE PRADO, Marcos; ZHU, Qiji Jim. Pseudo-Mathematics and Financial Charlatanism: The Effects of Backtest Overfitting on Out-of-Sample Performance. Notices of the American Mathematical Society. 2014, roč. 61, č. 5, s. 458–471. ISSN 0002-9920. Dostupné z: https://doi.org/10.1090/noti1105",
"HARVEY, Campbell R.; LIU, Yan; ZHU, Heqing. … and the Cross-Section of Expected Returns. The Review of Financial Studies. 2016, roč. 29, č. 1, s. 5–68. ISSN 0893-9454. Dostupné z: https://doi.org/10.1093/rfs/hhv059",
"PARDO, Robert. The Evaluation and Optimization of Trading Strategies. 2. vyd. Hoboken (NJ): John Wiley & Sons, 2008, s. [doplň stranu]. ISBN 978-0-470-12801-5. Dostupné z: https://books.google.com/books?isbn=9780470128015",
"EFRON, Bradley. Bootstrap Methods: Another Look at the Jackknife. The Annals of Statistics. 1979, roč. 7, č. 1, s. 1–26. ISSN 0090-5364. Dostupné z: https://doi.org/10.1214/aos/1176344552",
"SHARPE, William F. Mutual Fund Performance. The Journal of Business. 1966, roč. 39, č. 1, s. 119–138. ISSN 0021-9398. Dostupné z: https://doi.org/10.1086/294846",
"EFRON, Bradley; TIBSHIRANI, Robert J. An Introduction to the Bootstrap. New York: Chapman & Hall, 1993, s. [doplň stranu]. ISBN 978-0-412-04231-7. Dostupné z: https://books.google.com/books?isbn=9780412042317",
"METROPOLIS, Nicholas; ULAM, Stanislaw. The Monte Carlo Method. Journal of the American Statistical Association. 1949, roč. 44, č. 247, s. 335–341. ISSN 0162-1459. Dostupné z: https://doi.org/10.1080/01621459.1949.10483310",
"BAILEY, David H.; LÓPEZ DE PRADO, Marcos. The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting, and Non-Normality. The Journal of Portfolio Management. 2014, roč. 40, č. 5, s. 94–107. ISSN 0095-4918. Dostupné z: https://doi.org/10.3905/jpm.2014.40.5.094",
"LÓPEZ DE PRADO, Marcos. Advances in Financial Machine Learning. Hoboken (NJ): John Wiley & Sons, 2018, s. [doplň stranu]. ISBN 978-1-119-48208-6. Dostupné z: https://books.google.com/books?isbn=9781119482086",
"QuantConnect Corporation. LEAN Algorithmic Trading Engine [software, online]. 2023 [cit. 2026-07-22]. Dostupné z: https://www.quantconnect.com",
"TradingView. Pine Script (verze 5) [software, online]. 2023 [cit. 2026-07-22]. Dostupné z: https://www.tradingview.com",
]],
];

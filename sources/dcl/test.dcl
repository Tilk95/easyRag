$!======================================================================
$!  EXEMPLE_BATCH.COM
$!  Objectif : Script DCL de démonstration pour tester un mini-RAG (FTS+chunks)
$!  - Détection/validation paramètres
$!  - Vérification existence fichier d'entrée
$!  - Journaux, copies, et appels de sous-procédures
$!  - Gestion d'erreurs via ON ERROR + codes de sortie
$!======================================================================

$ SET NOON
$ SET VERIFY
$ ON ERROR THEN GOTO ERR_HANDLER

$!----------------------------------------------------------------------
$! SECTION: Initialisation
$!----------------------------------------------------------------------

$ INIT:
$   WRITE SYS$OUTPUT "=== DEMO: Batch DCL - Début ==="
$   START_TIME = F$TIME()

$   DEFAULT_DIR = F$ENVIRONMENT("DEFAULT")
$   WRITE SYS$OUTPUT "Default = ''DEFAULT_DIR'"

$   IF P1 .EQS. "" THEN GOTO USAGE
$   INFILE  = P1
$   OUTDIR  = P2
$   IF OUTDIR .EQS. "" THEN OUTDIR = DEFAULT_DIR

$   WRITE SYS$OUTPUT "INFILE = ''INFILE'"
$   WRITE SYS$OUTPUT "OUTDIR = ''OUTDIR'"

$!----------------------------------------------------------------------
$! SECTION: Vérification fichier d'entrée
$!----------------------------------------------------------------------

$ CHECK_INPUT:
$   IF F$SEARCH(INFILE) .EQS. "" THEN GOTO ERR_NOFILE
$   WRITE SYS$OUTPUT "OK: fichier trouvé: ''INFILE'"

$!----------------------------------------------------------------------
$! SECTION: Préparation répertoires / noms
$!----------------------------------------------------------------------

$ PREPARE:
$   OUTFILE = OUTDIR + "DEMO_OUT_" + F$EXTRACT(0, 8, F$CVTIME(F$TIME(), "ABSOLUTE", "DATE")) + ".TXT"
$   LOGFILE = OUTDIR + "DEMO_LOG.TXT"
$   WRITE SYS$OUTPUT "OUTFILE = ''OUTFILE'"
$   WRITE SYS$OUTPUT "LOGFILE = ''LOGFILE'"

$   ! Exemple de traduction de nom logique
$   TMPROOT = F$TRNLNM("SYS$SCRATCH")
$   IF TMPROOT .EQS. "" THEN TMPROOT = OUTDIR
$   TMPFILE = TMPROOT + "DEMO_TMP.DAT"

$!----------------------------------------------------------------------
$! SECTION: Traitement principal (simulé)
$!----------------------------------------------------------------------

$ PROCESS:
$   WRITE SYS$OUTPUT "Traitement: copie INFILE vers TMPFILE"
$   COPY 'INFILE' 'TMPFILE'

$   WRITE SYS$OUTPUT "Traitement: génération OUTFILE"
$   CREATE 'OUTFILE'
$   OPEN/APPEND OUTH 'OUTFILE'
$   WRITE OUTH "DEMO RESULT"
$   WRITE OUTH "Source: ''INFILE'"
$   WRITE OUTH "Tmp:    ''TMPFILE'"
$   CLOSE OUTH

$   WRITE SYS$OUTPUT "Traitement: append du résultat dans LOGFILE"
$   IF F$SEARCH(LOGFILE) .EQS. "" THEN CREATE 'LOGFILE'
$   APPEND 'OUTFILE' 'LOGFILE'

$!----------------------------------------------------------------------
$! SECTION: Appel d'une sous-procédure (exemple)
$!----------------------------------------------------------------------

$ CALL_SUB:
$   WRITE SYS$OUTPUT "Appel d'une procédure externe (démo)"
$

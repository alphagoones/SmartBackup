#!/bin/bash
# SmartBackup - Script d'installation automatique

set -e

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REPO_URL="https://raw.githubusercontent.com/votre-username/SmartBackup/main/smartbackup.py"
INSTALL_DIR="/usr/local/bin"
SCRIPT_NAME="smartbackup"

print_header() {
    echo -e "${BLUE}"
    echo "╔═══════════════════════════════════════╗"
    echo "║           SmartBackup Setup           ║"
    echo "║      Installation automatique         ║"
    echo "╚═══════════════════════════════════════╝"
    echo -e "${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

check_dependencies() {
    echo "Vérification des dépendances..."
    
    # Vérifier Python 3
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 n'est pas installé"
        exit 1
    fi
    print_success "Python 3 trouvé"
    
    # Vérifier curl ou wget
    if command -v curl &> /dev/null; then
        DOWNLOADER="curl -fsSL"
    elif command -v wget &> /dev/null; then
        DOWNLOADER="wget -qO-"
    else
        print_error "curl ou wget requis pour l'installation"
        exit 1
    fi
    print_success "Outil de téléchargement trouvé"
}

install_smartbackup() {
    echo "Installation de SmartBackup..."
    
    # Télécharger le script
    print_success "Téléchargement depuis GitHub..."
    $DOWNLOADER $REPO_URL > /tmp/smartbackup.py
    
    # Vérifier le téléchargement
    if [ ! -s /tmp/smartbackup.py ]; then
        print_error "Échec du téléchargement"
        exit 1
    fi
    
    # Rendre exécutable
    chmod +x /tmp/smartbackup.py
    
    # Installer
    if [ "$EUID" -ne 0 ]; then
        print_warning "Installation dans le répertoire utilisateur..."
        mkdir -p ~/.local/bin
        cp /tmp/smartbackup.py ~/.local/bin/smartbackup
        
        # Ajouter au PATH si nécessaire
        if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
            print_warning "Veuillez redémarrer votre terminal ou exécuter: source ~/.bashrc"
        fi
        
        INSTALL_PATH="~/.local/bin/smartbackup"
    else
        print_success "Installation système..."
        cp /tmp/smartbackup.py $INSTALL_DIR/smartbackup
        INSTALL_PATH="$INSTALL_DIR/smartbackup"
    fi
    
    # Nettoyer
    rm /tmp/smartbackup.py
    
    print_success "SmartBackup installé dans $INSTALL_PATH"
}

create_example_config() {
    echo "Création d'un exemple de configuration..."
    
    mkdir -p ~/.smartbackup/examples
    
    cat > ~/.smartbackup/examples/exemple_usage.sh << 'EOF'
#!/bin/bash
# Exemples d'utilisation de SmartBackup

echo "=== Exemples d'utilisation SmartBackup ==="

echo "1. Sauvegarde simple des documents:"
echo "smartbackup add documents /home/$USER/Documents --dest /backup"

echo ""
echo "2. Sauvegarde avec exclusions:"
echo "smartbackup add dev_projects /home/$USER/dev --dest /backup/dev --exclude '.git' 'node_modules' '*.log'"

echo ""
echo "3. Sauvegarde hebdomadaire automatique:"
echo "smartbackup add weekly_backup /home/$USER --dest /backup/weekly --schedule '0 2 * * 0'"

echo ""
echo "4. Installation de la tâche cron:"
echo "smartbackup install-cron weekly_backup"

echo ""
echo "5. Lister les configurations:"
echo "smartbackup list"

echo ""
echo "6. Lancer une sauvegarde:"
echo "smartbackup backup weekly_backup"
EOF
    
    chmod +x ~/.smartbackup/examples/exemple_usage.sh
    print_success "Exemples créés dans ~/.smartbackup/examples/"
}

show_completion() {
    echo ""
    print_success "Installation terminée avec succès !"
    echo ""
    echo -e "${BLUE}Prochaines étapes :${NC}"
    echo "1. Testez l'installation : smartbackup list"
    echo "2. Créez votre première configuration :"
    echo "   smartbackup add test ~/Documents --dest /tmp/backup"
    echo "3. Lancez une sauvegarde : smartbackup backup test"
    echo "4. Consultez les exemples : ~/.smartbackup/examples/"
    echo ""
    echo -e "${YELLOW}Documentation complète :${NC}"
    echo "https://github.com/votre-username/SmartBackup"
}

main() {
    print_header
    check_dependencies
    install_smartbackup
    create_example_config
    show_completion
}

# Exécution du script
main "$@"

#!/usr/bin/env python3
"""
SmartBackup - Gestionnaire de sauvegarde intelligent pour Linux
Fonctionnalités :
- Sauvegarde incrémentielle automatique
- Compression intelligente
- Planification flexible
- Interface en ligne de commande intuitive
- Logs détaillés
- Support de plusieurs destinations (local, réseau)
"""

import os
import sys
import json
import shutil
import hashlib
import argparse
import datetime
import subprocess
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
import logging

@dataclass
class BackupConfig:
    name: str
    source_dirs: List[str]
    destination: str
    schedule: str  # cron format
    compression: bool = True
    incremental: bool = True
    exclude_patterns: List[str] = None
    max_backups: int = 10

class SmartBackup:
    def __init__(self, config_path: str = "~/.smartbackup/config.json"):
        self.config_path = Path(config_path).expanduser()
        self.config_dir = self.config_path.parent
        self.log_dir = self.config_dir / "logs"
        self.backup_index_path = self.config_dir / "backup_index.json"
        
        # Créer les répertoires nécessaires
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(exist_ok=True)
        
        # Configuration du logging
        self.setup_logging()
        
        # Charger la configuration
        self.configs: Dict[str, BackupConfig] = self.load_configs()
        
        # Index des sauvegardes
        self.backup_index = self.load_backup_index()

    def setup_logging(self):
        log_file = self.log_dir / f"smartbackup_{datetime.datetime.now().strftime('%Y%m%d')}.log"
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)

    def load_configs(self) -> Dict[str, BackupConfig]:
        if not self.config_path.exists():
            return {}
        
        try:
            with open(self.config_path, 'r') as f:
                data = json.load(f)
                return {name: BackupConfig(**config) for name, config in data.items()}
        except Exception as e:
            self.logger.error(f"Erreur lors du chargement de la configuration: {e}")
            return {}

    def save_configs(self):
        with open(self.config_path, 'w') as f:
            json.dump({name: asdict(config) for name, config in self.configs.items()}, f, indent=2)

    def load_backup_index(self) -> Dict:
        if not self.backup_index_path.exists():
            return {}
        
        try:
            with open(self.backup_index_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Erreur lors du chargement de l'index: {e}")
            return {}

    def save_backup_index(self):
        with open(self.backup_index_path, 'w') as f:
            json.dump(self.backup_index, f, indent=2)

    def add_config(self, name: str, source_dirs: List[str], destination: str, 
                   schedule: str = "0 2 * * *", **kwargs):
        """Ajouter une nouvelle configuration de sauvegarde"""
        config = BackupConfig(
            name=name,
            source_dirs=source_dirs,
            destination=destination,
            schedule=schedule,
            **kwargs
        )
        
        self.configs[name] = config
        self.save_configs()
        self.logger.info(f"Configuration '{name}' ajoutée avec succès")

    def calculate_file_hash(self, filepath: Path) -> str:
        """Calculer le hash MD5 d'un fichier pour détecter les changements"""
        hash_md5 = hashlib.md5()
        try:
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception:
            return ""

    def get_file_info(self, filepath: Path) -> Dict:
        """Obtenir les informations d'un fichier"""
        try:
            stat = filepath.stat()
            return {
                'size': stat.st_size,
                'mtime': stat.st_mtime,
                'hash': self.calculate_file_hash(filepath)
            }
        except Exception:
            return {}

    def should_backup_file(self, filepath: Path, config_name: str) -> bool:
        """Déterminer si un fichier doit être sauvegardé (pour sauvegarde incrémentielle)"""
        file_key = str(filepath)
        config_index = self.backup_index.get(config_name, {})
        
        if file_key not in config_index:
            return True
        
        current_info = self.get_file_info(filepath)
        stored_info = config_index[file_key]
        
        return (current_info.get('hash') != stored_info.get('hash') or
                current_info.get('mtime') != stored_info.get('mtime'))

    def create_backup(self, config_name: str) -> bool:
        """Créer une sauvegarde selon la configuration donnée"""
        if config_name not in self.configs:
            self.logger.error(f"Configuration '{config_name}' non trouvée")
            return False

        config = self.configs[config_name]
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Créer le répertoire de destination
        dest_path = Path(config.destination) / f"{config_name}_{timestamp}"
        dest_path.mkdir(parents=True, exist_ok=True)

        self.logger.info(f"Début de la sauvegarde '{config_name}' vers {dest_path}")
        
        files_backed_up = 0
        total_size = 0
        
        # Préparer l'index pour cette configuration
        if config_name not in self.backup_index:
            self.backup_index[config_name] = {}

        for source_dir in config.source_dirs:
            source_path = Path(source_dir).expanduser()
            
            if not source_path.exists():
                self.logger.warning(f"Répertoire source non trouvé: {source_path}")
                continue
            
            self.logger.info(f"Sauvegarde du répertoire: {source_path}")
            
            for root, dirs, files in os.walk(source_path):
                root_path = Path(root)
                
                # Appliquer les patterns d'exclusion
                if self.should_exclude(root_path, config.exclude_patterns):
                    continue
                
                for file in files:
                    filepath = root_path / file
                    
                    if self.should_exclude(filepath, config.exclude_patterns):
                        continue
                    
                    # Vérifier si le fichier doit être sauvegardé (mode incrémentiel)
                    if config.incremental and not self.should_backup_file(filepath, config_name):
                        continue
                    
                    # Créer la structure de répertoires dans la destination
                    rel_path = filepath.relative_to(source_path)
                    dest_file_path = dest_path / source_path.name / rel_path
                    dest_file_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    try:
                        shutil.copy2(filepath, dest_file_path)
                        files_backed_up += 1
                        total_size += filepath.stat().st_size
                        
                        # Mettre à jour l'index
                        self.backup_index[config_name][str(filepath)] = self.get_file_info(filepath)
                        
                    except Exception as e:
                        self.logger.error(f"Erreur lors de la copie de {filepath}: {e}")

        # Compresser si demandé
        if config.compression:
            self.compress_backup(dest_path)
        
        # Nettoyer les anciennes sauvegardes
        self.cleanup_old_backups(config)
        
        # Sauvegarder l'index
        self.save_backup_index()
        
        self.logger.info(f"Sauvegarde terminée: {files_backed_up} fichiers, {total_size / (1024*1024):.2f} MB")
        return True

    def should_exclude(self, path: Path, exclude_patterns: Optional[List[str]]) -> bool:
        """Vérifier si un chemin doit être exclu"""
        if not exclude_patterns:
            return False
        
        path_str = str(path)
        return any(pattern in path_str for pattern in exclude_patterns)

    def compress_backup(self, backup_path: Path):
        """Compresser une sauvegarde"""
        self.logger.info(f"Compression de {backup_path}")
        try:
            archive_path = backup_path.with_suffix('.tar.gz')
            subprocess.run([
                'tar', '-czf', str(archive_path), 
                '-C', str(backup_path.parent), backup_path.name
            ], check=True)
            
            # Supprimer le répertoire non compressé
            shutil.rmtree(backup_path)
            self.logger.info(f"Sauvegarde compressée: {archive_path}")
        except Exception as e:
            self.logger.error(f"Erreur lors de la compression: {e}")

    def cleanup_old_backups(self, config: BackupConfig):
        """Nettoyer les anciennes sauvegardes"""
        dest_dir = Path(config.destination)
        if not dest_dir.exists():
            return
        
        # Lister toutes les sauvegardes de cette configuration
        backups = []
        for item in dest_dir.iterdir():
            if item.name.startswith(f"{config.name}_"):
                backups.append(item)
        
        # Trier par date de modification (plus récent en premier)
        backups.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        # Supprimer les sauvegardes en excès
        if len(backups) > config.max_backups:
            for backup in backups[config.max_backups:]:
                try:
                    if backup.is_dir():
                        shutil.rmtree(backup)
                    else:
                        backup.unlink()
                    self.logger.info(f"Ancienne sauvegarde supprimée: {backup}")
                except Exception as e:
                    self.logger.error(f"Erreur lors de la suppression de {backup}: {e}")

    def list_configs(self):
        """Lister toutes les configurations"""
        if not self.configs:
            print("Aucune configuration trouvée.")
            return
        
        print("Configurations de sauvegarde:")
        print("-" * 50)
        for name, config in self.configs.items():
            print(f"Nom: {name}")
            print(f"  Sources: {', '.join(config.source_dirs)}")
            print(f"  Destination: {config.destination}")
            print(f"  Planification: {config.schedule}")
            print(f"  Compression: {'Oui' if config.compression else 'Non'}")
            print(f"  Incrémentiel: {'Oui' if config.incremental else 'Non'}")
            print()

    def install_cron(self, config_name: str):
        """Installer une tâche cron pour une configuration"""
        if config_name not in self.configs:
            self.logger.error(f"Configuration '{config_name}' non trouvée")
            return False
        
        config = self.configs[config_name]
        script_path = Path(__file__).absolute()
        
        cron_line = f"{config.schedule} {sys.executable} {script_path} backup {config_name}"
        
        try:
            # Ajouter à crontab
            result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
            current_crontab = result.stdout if result.returncode == 0 else ""
            
            if cron_line not in current_crontab:
                new_crontab = current_crontab + cron_line + "\n"
                subprocess.run(['crontab'], input=new_crontab, text=True, check=True)
                self.logger.info(f"Tâche cron installée pour '{config_name}'")
            else:
                self.logger.info(f"Tâche cron déjà présente pour '{config_name}'")
            
            return True
        except Exception as e:
            self.logger.error(f"Erreur lors de l'installation de la tâche cron: {e}")
            return False

def main():
    parser = argparse.ArgumentParser(description="SmartBackup - Gestionnaire de sauvegarde intelligent")
    subparsers = parser.add_subparsers(dest='command', help='Commandes disponibles')
    
    # Commande add
    add_parser = subparsers.add_parser('add', help='Ajouter une configuration')
    add_parser.add_argument('name', help='Nom de la configuration')
    add_parser.add_argument('sources', nargs='+', help='Répertoires sources')
    add_parser.add_argument('--dest', required=True, help='Répertoire de destination')
    add_parser.add_argument('--schedule', default='0 2 * * *', help='Planification cron (défaut: 2h du matin)')
    add_parser.add_argument('--no-compression', action='store_true', help='Désactiver la compression')
    add_parser.add_argument('--no-incremental', action='store_true', help='Désactiver le mode incrémentiel')
    add_parser.add_argument('--exclude', nargs='*', help='Patterns à exclure')
    add_parser.add_argument('--max-backups', type=int, default=10, help='Nombre maximum de sauvegardes à conserver')
    
    # Commande backup
    backup_parser = subparsers.add_parser('backup', help='Lancer une sauvegarde')
    backup_parser.add_argument('name', help='Nom de la configuration')
    
    # Commande list
    subparsers.add_parser('list', help='Lister les configurations')
    
    # Commande install-cron
    cron_parser = subparsers.add_parser('install-cron', help='Installer une tâche cron')
    cron_parser.add_argument('name', help='Nom de la configuration')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    backup_manager = SmartBackup()
    
    if args.command == 'add':
        backup_manager.add_config(
            name=args.name,
            source_dirs=args.sources,
            destination=args.dest,
            schedule=args.schedule,
            compression=not args.no_compression,
            incremental=not args.no_incremental,
            exclude_patterns=args.exclude,
            max_backups=args.max_backups
        )
        print(f"Configuration '{args.name}' ajoutée avec succès!")
        
    elif args.command == 'backup':
        success = backup_manager.create_backup(args.name)
        if success:
            print(f"Sauvegarde '{args.name}' terminée avec succès!")
        else:
            print(f"Erreur lors de la sauvegarde '{args.name}'")
            sys.exit(1)
            
    elif args.command == 'list':
        backup_manager.list_configs()
        
    elif args.command == 'install-cron':
        success = backup_manager.install_cron(args.name)
        if success:
            print(f"Tâche cron installée pour '{args.name}'")
        else:
            print(f"Erreur lors de l'installation de la tâche cron")
            sys.exit(1)

if __name__ == "__main__":
    main()

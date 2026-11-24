// lib/features/demandes/fichiers.dart
//
// Pièces jointes : choix d'une photo (appareil photo, galerie) ou d'un fichier,
// ouverture d'un document téléchargé (PDF, image…) avec l'application du téléphone.

import 'dart:io';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:open_filex/open_filex.dart';
import 'package:path_provider/path_provider.dart';

/// Fichier choisi : chemin local et nom d'origine
typedef FichierChoisi = ({String chemin, String nom});

/// Propose appareil photo, galerie ou fichier ; null si l'utilisateur renonce.
Future<FichierChoisi?> choisirPiece(BuildContext context) async {
  final source = await showModalBottomSheet<String>(
    context: context,
    builder: (c) => SafeArea(
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        ListTile(leading: const Icon(Icons.photo_camera_outlined), title: const Text('Prendre une photo'),
            onTap: () => Navigator.pop(c, 'camera')),
        ListTile(leading: const Icon(Icons.photo_library_outlined), title: const Text('Choisir dans la galerie'),
            onTap: () => Navigator.pop(c, 'galerie')),
        ListTile(leading: const Icon(Icons.attach_file_rounded), title: const Text('Choisir un fichier (PDF, Word, Excel…)'),
            onTap: () => Navigator.pop(c, 'fichier')),
      ]),
    ),
  );
  if (source == null) return null;
  if (source == 'fichier') {
    final r = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: const ['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx', 'xls', 'xlsx'],
    );
    final f = r?.files.single;
    return f?.path == null ? null : (chemin: f!.path!, nom: f.name);
  }
  final photo = await ImagePicker().pickImage(
    source: source == 'camera' ? ImageSource.camera : ImageSource.gallery,
    imageQuality: 80,
    maxWidth: 2400,
  );
  return photo == null ? null : (chemin: photo.path, nom: photo.name);
}

/// Enregistre les octets dans le dossier temporaire puis les ouvre.
/// Renvoie un message d'erreur si aucune application ne sait ouvrir le fichier.
Future<String?> ouvrirOctets(List<int> octets, String nom) async {
  final dossier = await getTemporaryDirectory();
  final propre = nom.replaceAll(RegExp(r'[^\w.\-]+'), '_');
  final fichier = File('${dossier.path}/$propre');
  await fichier.writeAsBytes(octets, flush: true);
  final r = await OpenFilex.open(fichier.path);
  return r.type == ResultType.done ? null : (r.message.isEmpty ? 'Aucune application pour ouvrir ce fichier.' : r.message);
}

String tailleLisible(dynamic octets) {
  final n = num.tryParse('$octets') ?? 0;
  if (n >= 1024 * 1024) return '${(n / 1024 / 1024).toStringAsFixed(1).replaceAll('.', ',')} Mo';
  if (n >= 1024) return '${(n / 1024).round()} Ko';
  return '$n o';
}

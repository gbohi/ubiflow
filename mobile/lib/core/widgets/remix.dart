// lib/core/widgets/remix.dart
//
// Icônes Remix (police assets/fonts/remixicon.ttf, la même que le web) :
// un type de demande ou une action a le même pictogramme partout.

import 'package:flutter/widgets.dart';

class Remix {
  Remix._();
  static const _f = 'Remixicon';

  static const roadMap = IconData(0xf08e, fontFamily: _f); // ri-road-map-line
  static const flightTakeoff = IconData(0xed43, fontFamily: _f); // ri-flight-takeoff-line
  static const refund2 = IconData(0xf066, fontFamily: _f); // ri-refund-2-line
  static const restaurant = IconData(0xf084, fontFamily: _f); // ri-restaurant-line
  static const moneyDollarCircle = IconData(0xef65, fontFamily: _f); // ri-money-dollar-circle-line
  static const closeCircle = IconData(0xeb97, fontFamily: _f); // ri-close-circle-line
  static const addCircle = IconData(0xea11, fontFamily: _f); // ri-add-circle-line
  static const fileList3 = IconData(0xecef, fontFamily: _f); // ri-file-list-3-line
  static const checkboxMultiple = IconData(0xeb89, fontFamily: _f); // ri-checkbox-multiple-line
  static const user = IconData(0xf264, fontFamily: _f); // ri-user-line
  static const home5 = IconData(0xee1f, fontFamily: _f); // ri-home-5-line
  static const notification3 = IconData(0xef94, fontFamily: _f); // ri-notification-3-line
  static const fileText = IconData(0xed0f, fontFamily: _f); // ri-file-text-line
  static const sendPlane = IconData(0xf0da, fontFamily: _f); // ri-send-plane-line
  static const edit = IconData(0xec86, fontFamily: _f); // ri-edit-line
  static const deleteBin = IconData(0xec2a, fontFamily: _f); // ri-delete-bin-line
  static const camera = IconData(0xeb31, fontFamily: _f); // ri-camera-line
  static const filePdf = IconData(0xecfd, fontFamily: _f); // ri-file-pdf-line
  static const arrowLeftS = IconData(0xea64, fontFamily: _f); // ri-arrow-left-s-line
  static const alarmWarning = IconData(0xea1d, fontFamily: _f); // ri-alarm-warning-line
  static const checkboxCircle = IconData(0xeb81, fontFamily: _f); // ri-checkbox-circle-line
  static const errorWarning = IconData(0xeca1, fontFamily: _f); // ri-error-warning-line
  static const time = IconData(0xf20f, fontFamily: _f); // ri-time-line
  static const wallet3 = IconData(0xf2ac, fontFamily: _f); // ri-wallet-3-line
  static const arrowGoBack = IconData(0xea58, fontFamily: _f); // ri-arrow-go-back-line
  static const dashboard3 = IconData(0xec12, fontFamily: _f); // ri-dashboard-3-line
  static const stack = IconData(0xf181, fontFamily: _f); // ri-stack-line
  static const handCoin = IconData(0xedf1, fontFamily: _f); // ri-hand-coin-line
  static const task = IconData(0xf1e8, fontFamily: _f); // ri-task-line
  static const loader2 = IconData(0xeec2, fontFamily: _f); // ri-loader-2-line
  static const checkDouble = IconData(0xeb79, fontFamily: _f); // ri-check-double-line
  static const userShared = IconData(0xf272, fontFamily: _f); // ri-user-shared-line
  static const settings3 = IconData(0xf0e6, fontFamily: _f); // ri-settings-3-line
  static const search = IconData(0xf0d1, fontFamily: _f); // ri-search-line
  static const question = IconData(0xf045, fontFamily: _f); // ri-question-line
  static const fileCopy = IconData(0xecd5, fontFamily: _f); // ri-file-copy-line
  static const calendar = IconData(0xeb27, fontFamily: _f); // ri-calendar-line
  static const check = IconData(0xeb7b, fontFamily: _f); // ri-check-line
  static const arrowRightS = IconData(0xea6e, fontFamily: _f); // ri-arrow-right-s-line

  static const addBox = IconData(0xea0f, fontFamily: _f); // ri-add-box-line
  static const bankCard = IconData(0xea92, fontFamily: _f); // ri-bank-card-line

  /// Classe CSS renvoyée par l'API (« ri-road-map-line ») → icône ; null si inconnue.
  static IconData? deClasse(String? classe) => _parClasse[classe];

  static const Map<String, IconData> _parClasse = {
    'ri-add-box-line': addBox,
    'ri-bank-card-line': bankCard,
    'ri-road-map-line': roadMap,
    'ri-flight-takeoff-line': flightTakeoff,
    'ri-refund-2-line': refund2,
    'ri-restaurant-line': restaurant,
    'ri-money-dollar-circle-line': moneyDollarCircle,
    'ri-close-circle-line': closeCircle,
    'ri-add-circle-line': addCircle,
    'ri-file-list-3-line': fileList3,
    'ri-checkbox-multiple-line': checkboxMultiple,
    'ri-user-line': user,
    'ri-home-5-line': home5,
    'ri-notification-3-line': notification3,
    'ri-file-text-line': fileText,
    'ri-send-plane-line': sendPlane,
    'ri-edit-line': edit,
    'ri-delete-bin-line': deleteBin,
    'ri-camera-line': camera,
    'ri-file-pdf-line': filePdf,
    'ri-arrow-left-s-line': arrowLeftS,
    'ri-alarm-warning-line': alarmWarning,
    'ri-checkbox-circle-line': checkboxCircle,
    'ri-error-warning-line': errorWarning,
    'ri-time-line': time,
    'ri-wallet-3-line': wallet3,
    'ri-arrow-go-back-line': arrowGoBack,
    'ri-dashboard-3-line': dashboard3,
    'ri-stack-line': stack,
    'ri-hand-coin-line': handCoin,
    'ri-task-line': task,
    'ri-loader-2-line': loader2,
    'ri-check-double-line': checkDouble,
    'ri-user-shared-line': userShared,
    'ri-settings-3-line': settings3,
    'ri-search-line': search,
    'ri-question-line': question,
    'ri-file-copy-line': fileCopy,
    'ri-calendar-line': calendar,
    'ri-check-line': check,
    'ri-arrow-right-s-line': arrowRightS,
  };
}

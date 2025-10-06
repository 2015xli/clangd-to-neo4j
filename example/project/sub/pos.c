// Welcome to the program. The declaration of the functions and the library used is in .h file
#include "../main.h"

CUSTOMER CurrentCustomer;
int isCustomerHasId;
INVENTORY inventoryHist[1000]; // Save 1000 Transaction per a purchase
int inventoryCounter[1000]; // Count the amount of each inventory
int inventoryHistRecordCount = 0;   // Iterator of inventoryHist
int histStart, histStop;   // Line pointer for printing the transaction list
double subTotal, tax, total, pointEarn, totalProfit, discount, pointUsed;
char promotionId[140];
double promotionPrice;
int savedToDatabase;
int screenStep = 0;

void cashierInterface (int customerIdNotFound) {
  //Interface that will ask for customer ID
    // Initial Values
    isCustomerHasId = 0;
    inventoryHistRecordCount = 0;
    subTotal = 0, tax = 0, total = 0, pointEarn = 0, totalProfit = 0;
    promotionPrice = 0;
    discount = 0;
    pointUsed = 0;
    savedToDatabase = 0;
    screenClear ();
    char buffer[140];
    sprintf (buffer, "Cashier: %s %s", Session.user.firstname, Session.user.lastname);
    banner (Setting.storeName, Setting.storeAddress, "", buffer);
    bannerBlankBorder ();
    sprintf (buffer, "My name is %s %.1s. and I am your cashier", Session.user.firstname, Session.user.lastname);
    bannerBlankBorderTextCen (buffer);
    bannerBlankBorder ();
    if ( customerIdNotFound )
        bannerBlankBorderTextCen ("Customer not found");
    else
        bannerBlankBorder ();
    bannerBlankBorderTextCen ("Please scan / enter in customer ID");
    for ( int i = 25; i > 0; i-- )
        bannerBlankBorder ();
    bannerBlankBorderTextCen ("Type 'Q' to quit  |  Press ENTER to skip  |  Type 'B' to back");
    bannerFullBorder ();
    bannerUserInput ();
    // Receives input + let user type in the member ID or type N or type ENTER or type B
    // Call this if the input is not N or B -> delay (5); cashierInterfaceInventory ();
    char customerId[MAX_LNG_ID];
    if ( superscanf (customerId)) {
        if ( strlen (customerId) == 1 ) {
            // User type the switch
            switch ( toupper (customerId[0])) {
                case 'Q':
                    terminate ();
                    break;
                case 'B':
                    switchHub ();
                    break;
                default:
                    cashierInterface (0);
            }
        } else {
            // User input the customerId
            if ( customerSelectById (customerId, CurrentCustomer.firstname, CurrentCustomer.lastname,
                                     &CurrentCustomer.gender, &CurrentCustomer.point, &CurrentCustomer.totalBuy)) {
                isCustomerHasId = 1;
                strcpy (CurrentCustomer.id, customerId);

                cashierInterfaceInventory (0);
            } else {
                cashierInterface (1);
            }
        }
    } else { // Press only ENTER to skip
        cashierInterfaceInventory (0);
    }
}

void cashierInterfaceInventory (int isError) {
  // Interface that will remove the item from the database
    screenClear ();
    char buffer1[140], buffer2[140];
    int maxItemOnScreen = 21;
    histStart = 0 + (inventoryHistRecordCount / (maxItemOnScreen + 1)) * maxItemOnScreen;
    histStop = inventoryHistRecordCount;
    sprintf (buffer1, "%s %s is serving you today", Session.user.firstname, Session.user.lastname);
    if ( isCustomerHasId )
        sprintf (buffer2, "Welcome back, K. %s %s", CurrentCustomer.firstname, CurrentCustomer.lastname);
    else
        sprintf (buffer2, "Welcome back, Customer");
    banner (Setting.storeName, Setting.storeAddress, buffer1, buffer2);
    bannerBlankBorder ();
    bannerBlankBorderTextLeft (
            " ID                 | Item name                                                                             | Count      | Price      "); // Keep these on forever
    bannerBlankBorderTextLeft (
            " ------------------ | ------------------------------------------------------------------------------------- | ---------- | ---------- ");
    // Following by LAST `maxItemOnScreen` items that have been scanned....
    int lineCounter = 0;
    int i = histStart;
    while ( i < histStop ) {
        printf ("::  %-18s | %-85s | %10d | %10.2lf  ::\n", inventoryHist[i].id, inventoryHist[i].name,
                inventoryCounter[i], inventoryCounter[i] * inventoryHist[i].price);
        i++;
        lineCounter++;
    }

    for ( ; lineCounter < maxItemOnScreen; lineCounter++ )
        bannerBlankBorderTextLeft (
                "                    |                                                                                       |            |          ");
    char text[140];
    bannerBlankBorder ();
    sprintf (text, "Sub Total %.2f", subTotal);
    bannerBlankBorderText (text); // Total Price - 7% (Shows only 2 significant point!!)
    sprintf (text, "Tax %.2f", tax);
    bannerBlankBorderText (text); // VAT calculated from total price
    sprintf (text, "Total %.2f", total);
    bannerBlankBorderText (text); // Total Price
    if ( isCustomerHasId ){
        sprintf (text, "Points you will earned %.2f", pointEarn);
        bannerBlankBorderText (text);
    } else
        bannerBlankBorder ();
    if ( isError )
        bannerBlankBorderTextCen ("No item in the inventory");
    else
        bannerBlankBorder ();
    bannerBlankBorderTextCen ("Type 'Q' to quit  |  Press ENTER to finish  |  Type 'V' to void");
    bannerFullBorder ();
    bannerUserInput ();
    // Buffer
    char inventoryName[MAX_LNG_SCREEN];
    double inventoryPrice;
    double inventoryProfit; // Profit per item
    unsigned int inventoryCategoryId; // Category ID
    unsigned int inventoryRemain;
    // Receives item ID -> Query on database -> Find a match (if stock = 0 means no match) -> Show a match -> Add price to the total -> Remove stock from DB of 1
    char inventoryIdInput[MAX_LNG_SCREEN];
    int isDuplicate;
    if ( superscanf (inventoryIdInput)) {
        if ( strlen (inventoryIdInput) == 1 ) { // User type the switch
            switch ( toupper (inventoryIdInput[0])) {
                case 'Q':
                    terminate ();
                    break;
                case 'V':
                    cashierInterface (0);
                    break;
                default:
                    cashierInterfaceInventory (0);
            }
        } else { // User scan the inventory's barcode
            if ( inventorySelectById (inventoryIdInput, inventoryName, &inventoryPrice, &inventoryProfit,
                                      &inventoryCategoryId, &inventoryRemain)) {
                isDuplicate = 0;
                for ( int i = 0; i < inventoryHistRecordCount; i++ ) {
                    if ( strcmp (inventoryHist[i].id, inventoryIdInput) == 0 ) {
                        isDuplicate = 1; // Duplicate inventory detector
                        inventoryHist[i].remain--;
                        inventoryCounter[i]++;
                        break;
                    }
                }
                if ( !isDuplicate ) {
                    strcpy (inventoryHist[inventoryHistRecordCount].id, inventoryIdInput);
                    strcpy (inventoryHist[inventoryHistRecordCount].name, inventoryName);
                    inventoryHist[inventoryHistRecordCount].price = inventoryPrice;
                    inventoryHist[inventoryHistRecordCount].profit = inventoryProfit;
                    inventoryHist[inventoryHistRecordCount].categoryId = inventoryCategoryId;
                    inventoryHist[inventoryHistRecordCount].remain = inventoryRemain - 1;
                    inventoryCounter[inventoryHistRecordCount] = 1;
                    inventoryHistRecordCount++;
                }
                total += inventoryPrice;
                tax = total * 0.07;
                subTotal = total - tax;
                pointEarn = Setting.priceToPoint * total;
                totalProfit += inventoryProfit;
                cashierInterfaceInventory (0);
            } else
                cashierInterfaceInventory (1);
        }
    } else
        cashierInterfaceDiscount (0);
}

void cashierInterfaceDiscount (int errorCode) {
  // Interface that will ask for discount (voucher and points)
    if ( inventoryHistRecordCount == 0 ) { // If no input of inventory then return back to add the inventory again
        cashierInterfaceInventory (0);
    screenClear ();
    char buffer1[140], buffer2[140];
    sprintf (buffer1, "%s %s is serving you today", Session.user.firstname, Session.user.lastname);
    if ( isCustomerHasId )
        sprintf (buffer2, "Welcome back, K. %s %s", CurrentCustomer.firstname, CurrentCustomer.lastname);
    else
        sprintf (buffer2, "Welcome back, Customer");
    banner (Setting.storeName, Setting.storeAddress, buffer1, buffer2);
    bannerBlankBorder ();
    bannerBlankBorderTextCen ("Scan a Voucher / Discount Code");
    bannerBlankBorder ();
    char text[140];
    int promotionStatus; // 0 = Used | 1 = Active
    if ( isCustomerHasId ) { // Customer is a Member
        sprintf (text, "You have %.2lf points", CurrentCustomer.point);
        bannerBlankBorderTextCen (text);
        if ( errorCode == 1 ) {
            for ( int i = 26; i > 0; i-- )
                bannerBlankBorder ();
            bannerBlankBorderTextCen ("Invalid Promotion Code, Please try another one");
        } else
            for ( int i = 26; i > 0; i-- )
                bannerBlankBorder ();
        bannerBlankBorderTextCen (
                "Type 'Q' to quit  |  Type 'V' to void  |  Press ENTER to skip  |  Type 'P' to use point  |  Type 'A' to add more item");
        bannerFullBorder ();
        bannerUserInput ();
        if ( superscanf (promotionId)) {
            if ( strlen (promotionId) == 1 ) {
                switch ( toupper (promotionId[0])) {
                    case 'Q':
                        terminate ();
                        break;
                    case 'V':
                        cashierInterface (0);
                        break;
                    case 'P':
                        // Use point
                        cashierInterfaceResult (1);
                        break;
                    case 'A':
                        cashierInterfaceInventory (0);
                        break;
                    default:
                        cashierInterfaceDiscount (0);
                }
            } else { // Use Voucher
                if ( promotionSelectById (promotionId, &promotionPrice, &promotionStatus) && promotionStatus == 1 ) {
                    discount = promotionPrice;
                    cashierInterfaceResult (0);
                } else
                    cashierInterfaceDiscount (1);
            }
        } else { // Skipping
            cashierInterfaceResult (0);
        }
    } else { // Customer is not a member
        for ( int i = 27; i > 0; i-- )
            bannerBlankBorder ();
        bannerBlankBorderTextCen (
                "Type 'Q' to quit  |  Type 'V' to void  |  Press ENTER to skip  | Type 'A' to add more item");
        bannerFullBorder ();
        bannerUserInput ();
        if ( superscanf (promotionId)) {
            if ( strlen (promotionId) == 1 ) { // Use Command
                switch ( toupper (promotionId[0])) {
                    case 'Q':
                        terminate ();
                        break;
                    case 'V':
                        cashierInterface (0);
                        break;
                    case 'A':
                        cashierInterfaceInventory (0);
                        break;
                    default:
                        cashierInterfaceDiscount (0);
                }
            } else { // Use Voucher
                if ( promotionSelectById (promotionId, &promotionPrice, &promotionStatus) && promotionStatus == 1 ) {
                    discount = promotionPrice;
                    cashierInterfaceResult (0);
                } else
                    cashierInterfaceDiscount (1);
            }
        } else {
            cashierInterfaceResult (0);
        }
    }
}
}

void cashierInterfaceResult (int usePoint) {
  // Interface that will show the total (just like the receipt)
    screenClear ();
    // Saving the purchase into DB ----------------------------------------------------------
    int i, j;
    if ( !savedToDatabase ) { // Doing this one time !!!
        if ( usePoint ) { // Use point
            double discountByPoint =
                    CurrentCustomer.point / Setting.pointToPrice; // Money that will be use to discount from totalPrice
            if ( discountByPoint <= total ) {
                discount = discountByPoint;
                pointUsed = CurrentCustomer.point;
                customerUpdatePoint (CurrentCustomer.id, 0);
            } else {
                discount = total;
                pointUsed = Setting.pointToPrice * total;
                customerUpdatePoint (CurrentCustomer.id, Setting.pointToPrice * total);
            }
        } else if ( discount > 0 ) {
            // Use Voucher + Change status of voucher from Active -> Used
            promotionUpdateStatus (promotionId, 0);
            // Discount boundary
            discount = (discount < total) ? discount : total;
        }
        // Saving all transactions into the Database
        for ( i = 0; i < inventoryHistRecordCount; i++ ) {
            // Decreasing items the in stock
            inventoryUpdateRemain (inventoryHist[i].id, inventoryHist[i].remain);
            for ( j = 0; j < inventoryCounter[i]; j++ )
                transactionInsert (RecordCount.purchase, inventoryHist[i].id);
        }
        // Update total points & total buy of customer
        if ( isCustomerHasId ) { // If customer is a member
            customerUpdatePoint (CurrentCustomer.id, CurrentCustomer.point + pointEarn - pointUsed);
            customerUpdatetotalBuy (CurrentCustomer.id, CurrentCustomer.totalBuy + total - discount);
        }
        // Saving a purchase into the Database
        if ( isCustomerHasId )
            purchaseInsert (total, discount, totalProfit, CurrentCustomer.id, Session.user.id);
        else
            purchaseInsert (total, discount, totalProfit, "", Session.user.id);
        savedToDatabase = 1;
    }
    char buffer1[140], buffer2[140];
    int maxItemOnScreen = 18;
    histStart = 0 + screenStep;
    histStop = inventoryHistRecordCount;
    sprintf (buffer1, "%s %s is serving you today", Session.user.firstname, Session.user.lastname);
    if ( isCustomerHasId )
        sprintf (buffer2, "Welcome back, K. %s %s", CurrentCustomer.firstname, CurrentCustomer.lastname);
    else
        sprintf (buffer2, "Welcome back, Customer");
    banner (Setting.storeName, Setting.storeAddress, buffer1, buffer2);
    char text[140];
    bannerBlankBorder ();
    bannerBlankBorderTextLeft (
            " ID                 | Item name                                                                          | Count       | Price        "); // Keep these on forever
    bannerBlankBorderTextLeft (
            " ------------------ | ---------------------------------------------------------------------------------- | ----------- | ------------ ");
    // Shows a total of 25 item at a time. Press ENTER to go to the next page
    int lineCounter = 0;
    i = histStart;
    while ( i < histStop ) {
        if ( lineCounter == maxItemOnScreen )
            break;
        printf ("::  %-18s | %-82s | %11d | %12.2lf  ::\n", inventoryHist[i].id, inventoryHist[i].name,
                inventoryCounter[i], inventoryCounter[i] * inventoryHist[i].price);
        i++;
        lineCounter++;
    }
    for ( ; lineCounter < maxItemOnScreen; lineCounter++ )
        bannerBlankBorderTextLeft (
                "                    |                                                                                    |             |            ");
    if ( isCustomerHasId ) {
        // If customer is a member
        bannerBlankBorderText ("|----------Membership----------| |----------Purchase---------|");
        strcpy (text, "");
        sprintf (text, "| Points you have   : %8.2f | | Sub Total   : %11.2f |", CurrentCustomer.point, subTotal);
        bannerBlankBorderText (text);
        sprintf (text, "| Points you used   : %8.2f | | VAT         : %11.2f |", pointUsed, tax);
        bannerBlankBorderText (text);
        strcpy (text, "");
        sprintf (text, "| Points you earn   : %8.2f | | Discount    : %+11.2f |", pointEarn, -discount);
        bannerBlankBorderText (text);
        bannerBlankBorderText ("|______________________________| |___________________________|");
        sprintf (text, "| Total             : %8.2f | | Total       : %11.2f |", CurrentCustomer.point - pointUsed + pointEarn, total - discount);
    } else {
        // If customer is not a member
        bannerBlankBorderText ("|----------Purchase---------|");
        strcpy (text, "");
        sprintf (text, "| Sub Total   : %11.2f |", subTotal);
        bannerBlankBorderText (text);
        sprintf (text, "| VAT         : %11.2f |", tax);
        bannerBlankBorderText (text);
        strcpy (text, "");
        sprintf (text, "| Discount    : %+11.2f |", -discount);
        bannerBlankBorderText (text);
        bannerBlankBorderText ("|___________________________|");
        sprintf (text, "| Total       : %11.2f |", total - discount);
    }
    bannerBlankBorderText (text);
    bannerBlankBorderTextCen ("_______________________________________________________________");
    strcpy (text, "");
    sprintf (text, "THANK YOU FOR SHOPPING AT %s", Setting.storeName);
    bannerBlankBorderTextCen (text);
    bannerBlankBorder ();
    if ( screenStep < inventoryHistRecordCount - maxItemOnScreen )
        bannerBlankBorderTextCen (
                "Type 'Q' to quit  |  Press ENTER to view more  |  Type 'V' to skip (Finish purchase)");
    else
        bannerBlankBorderTextCen ("Type 'Q' to quit  |  Press ENTER to finish purchase");
    bannerFullBorder ();
    bannerUserInput ();
    char userInput[5];
    if ( superscanf (userInput)) {
        switch ( toupper (userInput[0])) {
            case 'V':
                cashierInterface (0);
                break;
            case 'Q':
                switchHub ();
                break;
            default:
                cashierInterfaceResult (usePoint);
        }
    } else { // Press ENTER
        if ( screenStep < inventoryHistRecordCount - maxItemOnScreen ) {
            screenStep++;
            cashierInterfaceResult (0);
        } else
            cashierInterface (0);
    }
}

// Welcome to the program. The declaration of the functions and the library used is in .h file
#include "main.h"

// Path to Database file
const char *personnelDatabaseFile = "Database/personnel.db";
const char *inventoryDatabaseFile = "Database/inventory.db";
const char *categoryDatabaseFile = "Database/category.db";
const char *transactionDatabaseFile = "Database/transaction.db";
const char *purchaseDatabaseFile = "Database/purchase.db";
const char *customerDatabaseFile = "Database/customer.db";
const char *promotionDatabaseFile = "Database/promotion.db";
const char *settingDatabaseFile = "Database/setting.db";

void initDatabase () {
    // Database Initial
    personnelDatabase ();
    inventoryDatabase ();
    categoryDatabase ();
    transactionDatabase ();
    purchaseDatabase ();
    customerDatabase ();
    promotionDatabase ();
    settingDatabase ();

    // Database Seeding
    personnelFileRead ();
    inventoryFileRead ();
    categoryFileRead ();
    transactionFileRead ();
    purchaseFileRead ();
    customerFileRead ();
    promotionFileRead ();
    settingFileRead ();
}

void personnelDatabase () {
    // Check a Database file existence, if it doesn't exist then create the new one.
    if ( !isFileExist (personnelDatabaseFile)) {
        fopen (personnelDatabaseFile, "w");
    }
}

void inventoryDatabase () {
    // Check a Database file existence, if it doesn't exist then create the new one.
    if ( !isFileExist (inventoryDatabaseFile)) {
        fopen (inventoryDatabaseFile, "w");
    }
}

void categoryDatabase () {
    // Check a Database file existence, if it doesn't exist then create the new one.
    if ( !isFileExist (categoryDatabaseFile)) {
        fopen (categoryDatabaseFile, "w");
    }
}

void transactionDatabase () {
    // Check a Database file existence, if it doesn't exist then create the new one.
    if ( !isFileExist (transactionDatabaseFile)) {
        fopen (transactionDatabaseFile, "w");
    }
}

void purchaseDatabase () {
    // Check a Database file existence, if it doesn't exist then create the new one.
    if ( !isFileExist (purchaseDatabaseFile)) {
        fopen (purchaseDatabaseFile, "w");
    }
}

void customerDatabase () {
    // Check a Database file existence, if it doesn't exist then create the new one.
    if ( !isFileExist (customerDatabaseFile)) {
        fopen (customerDatabaseFile, "w");
    }
}

void promotionDatabase () {
    // Check a Database file existence, if it doesn't exist then create the new one.
    if ( !isFileExist (promotionDatabaseFile)) {
        fopen (promotionDatabaseFile, "w");
    }
}

void settingDatabase () {
    // Check a Database file existence, if it doesn't exist then create the new one.
    if ( !isFileExist (settingDatabaseFile)) {
        fopen (settingDatabaseFile, "w");
    }
}

void personnelFileRead () {
    // Fetch records form a Database file to the program memory
    FILE *fp;                           // File Pointer
    int i = 0;
    fp = fopen (personnelDatabaseFile, "r");
    while ( fscanf (fp, "%s\t%[^\t]\t%[^\t]\t%d\t%[^\t]\t%[^\t]\t%[^\n]", Personnel[i].id, Personnel[i].firstname,
                    Personnel[i].lastname, &Personnel[i].role, Personnel[i].username, Personnel[i].password,
                    Personnel[i].barcodeToken) != EOF ) {
        i++;
    }
    RecordCount.personnel = i;          // Save a number of records to the Record Counter
    fclose (fp);
}

void inventoryFileRead () {
    // Fetch records form a Database file to the program memory
    FILE *fp;                           // File Pointer

    int i = 0;
    fp = fopen (inventoryDatabaseFile, "r");

    while ( fscanf (fp, "%s\t%[^\t]\t%lf\t%lf\t%u\t%u", Inventory[i].id, Inventory[i].name, &Inventory[i].price,
                    &Inventory[i].profit, &Inventory[i].categoryId, &Inventory[i].remain) != EOF ) {
        i++;
    }
    RecordCount.inventory = i;          // Save a number of records to the Record Counter
    fclose (fp);
}

void categoryFileRead () {
    // Fetch records form a Database file to the program memory
    FILE *fp;                           // File Pointer
    int i = 0;
    fp = fopen (categoryDatabaseFile, "r");
    while ( fscanf (fp, "%u\t%[^\n]", &Category[i].id, Category[i].name) != EOF ) {
        i++;
    }
    RecordCount.category = i;          // Save a number of records to the Record Counter
    fclose (fp);
}

void transactionFileRead () {
    FILE *fp;                           // File Pointer
    int i = 0;
    fp = fopen (transactionDatabaseFile, "r");
    while ( fscanf (fp, "%u\t%u\t%s\t%[^\t]\t%lf\t%lf\t%u\t%lu", &Transaction[i].id, &Transaction[i].purchaseId,
                    Transaction[i].inventoryId, Transaction[i].inventoryName, &Transaction[i].inventoryPrice,
                    &Transaction[i].inventoryProfit, &Transaction[i].inventoryCategoryId, &Transaction[i].timestamp) !=
            EOF ) {
        i++;
    }

    RecordCount.transaction = i;          // Save a number of records to the Record Counter
    fclose (fp);
}

void purchaseFileRead () {

    // Fetch records form a Database file to the program memory
    FILE *fp;                           // File Pointer

    int i = 0;
    fp = fopen (purchaseDatabaseFile, "r");

    while ( fscanf (fp, "%u\t%lf\t%lf\t%lf\t%s\t%s\t%lu", &Purchase[i].id, &Purchase[i].totalPrice,
                    &Purchase[i].totalDiscount, &Purchase[i].totalProfit, Purchase[i].customerId,
                    Purchase[i].personnelId, &Purchase[i].timestamp) != EOF ) {
        i++;
    }

    RecordCount.purchase = i;          // Save a number of records to the Record Counter
    fclose (fp);
}

void customerFileRead () {
    // Fetch records form a Database file to the program memory
    FILE *fp;                           // File Pointer
    int i = 0;
    fp = fopen (customerDatabaseFile, "r");
    while ( fscanf (fp, "%s\t%[^\t]\t%[^\t]\t%c\t%lf\t%lf", Customer[i].id, Customer[i].firstname, Customer[i].lastname,
                    &Customer[i].gender, &Customer[i].point, &Customer[i].totalBuy) != EOF ) {
        i++;
    }
    RecordCount.customer = i;          // Save a number of records to the Record Counter
    fclose (fp);
}

void promotionFileRead () {
    // Fetch records form a Database file to the program memory
    FILE *fp;                           // File Pointer
    int i = 0;
    fp = fopen (promotionDatabaseFile, "r");
    while ( fscanf (fp, "%s\t%lf\t%d", Promotion[i].id, &Promotion[i].price, &Promotion[i].status) != EOF ) {
        i++;
    }
    RecordCount.promotion = i;          // Save a number of records to the Record Counter
    fclose (fp);
}

void settingFileRead () {
    // Fetch records form a Database file to the program memory
    FILE *fp;                           // File Pointer
    fp = fopen (settingDatabaseFile, "r");
    fscanf (fp, "%[^\t]\t%[^\t]\t%lf\t%lf", Setting.storeName, Setting.storeAddress, &Setting.priceToPoint,
            &Setting.pointToPrice);
    fclose (fp);
}

void personnelFileWrite () {
    // Save all of the records to a database file
    FILE *fp;                   // File Pointer
    int numberOfRecords;        // Number of the records in a table
    numberOfRecords = RecordCount.personnel;
    fp = fopen (personnelDatabaseFile, "w+");
    for ( int i = 0; i < numberOfRecords; i++ )
        fprintf (fp, "%s\t%s\t%s\t%d\t%s\t%s\t%s\n", Personnel[i].id, Personnel[i].firstname, Personnel[i].lastname,
                 Personnel[i].role, Personnel[i].username, Personnel[i].password, Personnel[i].barcodeToken);
    fclose (fp);
}

void inventoryFileWrite () {
    // Save all of the records to a database file
    FILE *fp;                   // File Pointer
    int numberOfRecords;        // Number of the records in a table
    numberOfRecords = RecordCount.inventory;
    fp = fopen (inventoryDatabaseFile, "w+");
    for ( int i = 0; i < numberOfRecords; i++ )
        fprintf (fp, "%s\t%s\t%lf\t%lf\t%u\t%u\n", Inventory[i].id, Inventory[i].name, Inventory[i].price,
                 Inventory[i].profit, Inventory[i].categoryId, Inventory[i].remain);
    fclose (fp);
}

void categoryFileWrite () {
    // Save all of the records to a database file
    FILE *fp;                   // File Pointer
    int numberOfRecords;        // Number of the records in a table
    numberOfRecords = RecordCount.category;
    fp = fopen (categoryDatabaseFile, "w+");
    for ( int i = 0; i < numberOfRecords; i++ )
        fprintf (fp, "%u\t%s\n", Category[i].id, Category[i].name);
    fclose (fp);
}

void transactionFileWrite () {
    // Save all of the records to a database file
    FILE *fp;                   // File Pointer
    int numberOfRecords;        // Number of the records in a table
    numberOfRecords = RecordCount.transaction;
    fp = fopen (transactionDatabaseFile, "w+");
    for ( int i = 0; i < numberOfRecords; i++ )
        fprintf (fp, "%u\t%u\t%s\t%s\t%lf\t%lf\t%u\t%lu\n", Transaction[i].id, Transaction[i].purchaseId,
                 Transaction[i].inventoryId, Transaction[i].inventoryName, Transaction[i].inventoryPrice,
                 Transaction[i].inventoryProfit, Transaction[i].inventoryCategoryId, Transaction[i].timestamp);
    fclose (fp);
}

void purchaseFileWrite () {
    // Save all of the records to a database file
    FILE *fp;                   // File Pointer
    int numberOfRecords;        // Number of the records in a table
    numberOfRecords = RecordCount.purchase;
    fp = fopen (purchaseDatabaseFile, "w+");
    for ( int i = 0; i < numberOfRecords; i++ )
        fprintf (fp, "%u\t%lf\t%lf\t%lf\t%s\t%s\t%lu\n", Purchase[i].id, Purchase[i].totalPrice,
                 Purchase[i].totalDiscount, Purchase[i].totalProfit, Purchase[i].customerId, Purchase[i].personnelId,
                 Purchase[i].timestamp);
    fclose (fp);
}

void customerFileWrite () {
    // Save all of the records to a database file
    FILE *fp;                   // File Pointer
    int numberOfRecords;        // Number of the records in a table
    numberOfRecords = RecordCount.customer;
    fp = fopen (customerDatabaseFile, "w+");

    for ( int i = 0; i < numberOfRecords; i++ )
        fprintf (fp, "%s\t%s\t%s\t%c\t%lf\t%lf\n", Customer[i].id, Customer[i].firstname, Customer[i].lastname,
                 Customer[i].gender, Customer[i].point, Customer[i].totalBuy);
    fclose (fp);
}

void promotionFileWrite () {
    // Save all of the records to a database file
    FILE *fp;                   // File Pointer
    int numberOfRecords;        // Number of the records in a table
    numberOfRecords = RecordCount.promotion;
    fp = fopen (promotionDatabaseFile, "w+");
    for ( int i = 0; i < numberOfRecords; i++ )
        fprintf (fp, "%s\t%lf\t%d\n", Promotion[i].id, Promotion[i].price, Promotion[i].status);
    fclose (fp);
}

void settingFileWrite () {
    // Save all of the settings to a database file
    FILE *fp;               // File Pointer
    fp = fopen (settingDatabaseFile, "w+");
    fprintf (fp, "%s\t%s\t%lf\t%lf\n", Setting.storeName, Setting.storeAddress, Setting.priceToPoint,
             Setting.pointToPrice);
    fclose (fp);
}

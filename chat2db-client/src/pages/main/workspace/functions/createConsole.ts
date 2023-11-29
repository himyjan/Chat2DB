import { setWorkspaceTabList, setActiveConsoleId } from '@/pages/main/workspace/store/console';
import { useWorkspaceStore } from '@/pages/main/workspace/store';
import { ConsoleStatus, ConsoleOpenedStatus, WorkspaceTabType, DatabaseTypeCode } from '@/constants'
import historyService from '@/service/history';

interface ICreateConsoleParams { 
  name?: string;
  ddl?: string;
  dataSourceId?: number;
  dataSourceName?: string;
  databaseName?: string;
  schemaName?: string;
  type?: DatabaseTypeCode;
  operationType?: string;
}

const createConsole = (params: ICreateConsoleParams) => {
  const workspaceTabList = useWorkspaceStore.getState().workspaceTabList;

  const newConsole = {
    ...params,
    name: params.name || 'new console',
    ddl: params.ddl || '',
    status: ConsoleStatus.DRAFT,
    tabOpened: ConsoleOpenedStatus.IS_OPEN,
    operationType: WorkspaceTabType.CONSOLE,
    dataSourceId: params.dataSourceId,
    dataSourceName: params.dataSourceName,
  };

  historyService.createConsole(newConsole).then((res) => {
    const newList = [
      ...(workspaceTabList||[]),
      {
        id: res,
        title: newConsole.name,
        type: newConsole.operationType,
        uniqueData: {
          ...newConsole,
          databaseType: newConsole.type,
        },
      },
    ];
    setWorkspaceTabList(newList);
    setActiveConsoleId(res);
  });
}

export default createConsole;

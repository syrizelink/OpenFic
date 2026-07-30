import { Flex } from "@radix-ui/themes";

import { Spinner } from "./spinner";

export function PanelLayoutLoading() {
  return (
    <Flex
      align="center"
      justify="center"
      height="100%"
      className="panel-layout-loading"
    >
      <Spinner size={18} />
    </Flex>
  );
}
